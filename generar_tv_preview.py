#!/usr/bin/env python3
"""
Genera tv.html y opits.html con datos del día y habilita los links en el nav.
Uso standalone — no modifica informe_sla_fijo.py ni el flujo de Fijo.
Épica: BST-13120 | BST-13293 / BST-13294 / BST-13295
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.cloud import bigquery

PROJECT_ID   = "mm-datamart-kd"
SCRIPT_DIR   = Path(__file__).parent
REPORTES_DIR = SCRIPT_DIR / "reportes"
TZ           = ZoneInfo("Europe/Madrid")

# ─────────────────────────────────────────────────────────────────
# BIGQUERY
# ─────────────────────────────────────────────────────────────────
def run_query(client, sql_file):
    sql = (SCRIPT_DIR / sql_file).read_text(encoding="utf-8")
    return [dict(row) for row in client.query(sql).result()]


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def esc(v):
    if v is None:
        return "—"
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def kpi_color(pct):
    if pct >= 80:   return "#2E7D32"
    if pct >= 50:   return "#FF5900"
    return "#C62828"

def alerta_icon(alerta):
    return {"CRITICO": "🔴", "AVISO": "🟡", "OK": "🟢"}.get(alerta, "—")

def fmt_date(v):
    """Convierte datetime/date de BQ a dd/mm/yyyy."""
    if v is None:
        return "—"
    if hasattr(v, 'strftime'):
        return v.strftime("%d/%m/%Y")
    s = str(v)[:10]  # 'YYYY-MM-DD...' → solo fecha
    try:
        from datetime import date
        d = date.fromisoformat(s)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return s


# ─────────────────────────────────────────────────────────────────
# TV.HTML — tablas SATN2-ZL y Logística
# ─────────────────────────────────────────────────────────────────
def build_tv_rows(rows, modo):
    """Construye filas HTML. modo='base' o 'logistica'."""
    incumple_rows = [r for r in rows if r.get("estado_sla") == "INCUMPLE"]
    otros_rows    = [r for r in rows if r.get("estado_sla") != "INCUMPLE"]
    html = ""

    def fila(r, hidden_cls=""):
        clave   = esc(r.get("CLAVE"))
        horas   = r.get("horas_sin_gestion") or "—"
        display = esc(r.get("estado_display"))
        critico = ' class="row-critico"' if isinstance(horas, (int, float)) and horas > 96 else ""
        if modo == "base":
            subcateg    = esc(r.get("MOTIVO_SOLICITUD"))
            ult_gestion = fmt_date(r.get("fecha_ultima_gestion"))
        else:
            subcateg    = esc(r.get("estado_logistica"))
            ult_gestion = fmt_date(r.get("fecha_inicio_reloj"))
        return (
            f'<tr{critico}{hidden_cls} data-horas="{horas}">'
            f'<td><a href="https://tgjira.masmovil.com/browse/{clave}" target="_blank">{clave}</a></td>'
            f'<td>{subcateg}</td>'
            f'<td style="font-weight:{"700;color:#C62828" if horas != "—" and isinstance(horas,(int,float)) and horas > 24 else "normal"}">{horas}h</td>'
            f'<td>{ult_gestion}</td>'
            f'<td>{display}</td>'
            f'</tr>\n'
        )

    for r in incumple_rows:
        html += fila(r)

    if otros_rows:
        sec = "tv_base" if modo == "base" else "tv_log"
        html += (
            f'<tr class="toggle-row" data-sec="{sec}">'
            f'<td colspan="99" class="toggle-cell">▼ Ver {len(otros_rows)} tickets dentro de SLA / excluidos</td>'
            f'</tr>\n'
        )
        for r in otros_rows:
            html += fila(r, f' class="otros-row-{sec}" style="display:none"')

    if not rows:
        html = '<tr><td colspan="99" style="text-align:center;color:#999;padding:1.5rem">Sin tickets hoy</td></tr>\n'

    return html

def generate_tv_html(rows_base, rows_log, now):
    fecha_str = now.strftime("%d/%m/%Y")
    hora_str  = now.strftime("%H:%M")
    dia_str   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][now.weekday()]

    def kpis(rows, es_log=False):
        comp = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"] if es_log else rows
        inc  = len([r for r in comp if r.get("estado_sla") == "INCUMPLE"])
        pct  = round(100 * (len(comp) - inc) / len(comp), 1) if comp else 100.0
        return inc, len(comp), pct, kpi_color(pct)

    inc_b, tot_b, pct_b, col_b = kpis(rows_base)
    inc_l, tot_l, pct_l, col_l = kpis(rows_log, es_log=True)

    total_comp = tot_b + tot_l
    total_inc  = inc_b + inc_l
    pct_g      = round(100 * (total_comp - total_inc) / total_comp, 1) if total_comp else 100.0
    col_g      = kpi_color(pct_g)

    rows_base_html = build_tv_rows(rows_base, "base")
    rows_log_html  = build_tv_rows(rows_log,  "logistica")

    excluidos_b = len([r for r in rows_base if r.get("estado_sla") == "EXCLUIDO"])
    excluidos_l = len([r for r in rows_log  if r.get("estado_sla") == "EXCLUIDO"])

    return TV_HTML_TEMPLATE.format(
        fecha_str=fecha_str, hora_str=hora_str, dia_str=dia_str,
        col_g=col_g, pct_g=pct_g, total_inc=total_inc, total_comp=total_comp,
        col_b=col_b, pct_b=pct_b, inc_b=inc_b, tot_b=tot_b, excl_b=excluidos_b,
        col_l=col_l, pct_l=pct_l, inc_l=inc_l, tot_l=tot_l, excl_l=excluidos_l,
        rows_base=rows_base_html,
        rows_log=rows_log_html,
    )


# ─────────────────────────────────────────────────────────────────
# OPITS.HTML
# ─────────────────────────────────────────────────────────────────
def build_opit_rows(rows):
    if not rows:
        return '<tr><td colspan="8" style="text-align:center;color:#999;padding:1.5rem">Sin OPITs abiertos hoy</td></tr>\n'
    html = ""
    for r in rows:
        clave  = esc(r.get("CLAVE"))
        marca  = esc(r.get("MARCA"))
        opit   = esc(r.get("ISSUE_OPIT"))
        status = esc(r.get("OPIT_STATUS"))
        prio   = esc(r.get("PRIO_OPIT"))
        dias   = r.get("dias_opit_abierto", "—")
        alerta = r.get("alerta_opit", "OK")
        icon   = alerta_icon(alerta)
        resumen = esc(r.get("OPIT_SUMMARY"))
        fila_cls = ' class="row-critico"' if alerta == "CRITICO" else ""
        html += (
            f'<tr{fila_cls}>'
            f'<td><a href="https://tgjira.masmovil.com/browse/{clave}" target="_blank">{clave}</a></td>'
            f'<td>{marca}</td>'
            f'<td><a href="https://jiranext.masmovil.com/browse/{opit}" target="_blank">{opit}</a></td>'
            f'<td>{status}</td>'
            f'<td>{prio}</td>'
            f'<td style="font-weight:700">{dias}d</td>'
            f'<td style="font-size:1.1rem">{icon}</td>'
            f'<td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{resumen}">{resumen}</td>'
            f'</tr>\n'
        )
    return html

def generate_opits_html(rows_all, now):
    fecha_str = now.strftime("%d/%m/%Y")
    hora_str  = now.strftime("%H:%M")
    dia_str   = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][now.weekday()]

    rows_tv   = [r for r in rows_all if r.get("TIPO_SERVICIO") == "TV"]
    rows_fijo = [r for r in rows_all if r.get("TIPO_SERVICIO") != "TV"]

    criticos_tv   = len([r for r in rows_tv   if r.get("alerta_opit") == "CRITICO"])
    criticos_fijo = len([r for r in rows_fijo if r.get("alerta_opit") == "CRITICO"])
    avisos_tv     = len([r for r in rows_tv   if r.get("alerta_opit") == "AVISO"])
    avisos_fijo   = len([r for r in rows_fijo if r.get("alerta_opit") == "AVISO"])

    return OPITS_HTML_TEMPLATE.format(
        fecha_str=fecha_str, hora_str=hora_str, dia_str=dia_str,
        total_tv=len(rows_tv), total_fijo=len(rows_fijo),
        total_all=len(rows_all),
        criticos_tv=criticos_tv, avisos_tv=avisos_tv,
        criticos_fijo=criticos_fijo, avisos_fijo=avisos_fijo,
        rows_tv=build_opit_rows(rows_tv),
        rows_fijo=build_opit_rows(rows_fijo),
    )


# ─────────────────────────────────────────────────────────────────
# PARCHEAR NAV en global.html, fijo.html
# ─────────────────────────name───────────────────────────────────
def patch_nav(html_path, patches):
    """Reemplaza strings en un HTML existente."""
    if not html_path.exists():
        print(f"  [SKIP] {html_path.name} no existe")
        return
    content = html_path.read_text(encoding="utf-8")
    for old, new in patches:
        content = content.replace(old, new)
    html_path.write_text(content, encoding="utf-8")
    print(f"  [OK] Parcheado {html_path.name}")


NAV_TV_DISABLED  = '<a href="tv.html" class="disabled" title="Próximamente">TV</a>'
NAV_TV_ENABLED   = '<a href="tv.html">TV</a>'
NAV_OPITs_ENTRY  = '<li><a href="opits.html">OPITs</a></li>'

BTN_TV_DISABLED  = '<button class="product-tab" disabled title="Próximamente">TV</button>'
BTN_TV_ENABLED   = '<button class="product-tab" onclick="location.href=\'tv.html\'">TV</button>'

FOOTER_TV_PROX   = '<a href="tv.html">TV (próx.)</a>'
FOOTER_TV_OK     = '<a href="tv.html">Informe TV</a>'


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    now    = datetime.now(tz=TZ)
    client = bigquery.Client(project=PROJECT_ID)

    print("Ejecutando queries TV...")
    rows_base = run_query(client, "query_tv_base.sql")
    rows_log  = run_query(client, "query_tv_logistica.sql")
    print(f"  TV base: {len(rows_base)} tickets | TV logística: {len(rows_log)} tickets")

    print("Ejecutando query OPITs...")
    rows_opit = run_query(client, "query_opit.sql")
    tv_opit   = len([r for r in rows_opit if r.get("TIPO_SERVICIO") == "TV"])
    fijo_opit = len([r for r in rows_opit if r.get("TIPO_SERVICIO") != "TV"])
    print(f"  OPITs: {len(rows_opit)} total ({tv_opit} TV, {fijo_opit} Fijo)")

    REPORTES_DIR.mkdir(exist_ok=True)

    print("Generando tv.html...")
    tv_html = generate_tv_html(rows_base, rows_log, now)
    (REPORTES_DIR / "tv.html").write_text(tv_html, encoding="utf-8")
    print("  [OK] reportes/tv.html")

    print("Generando opits.html...")
    opits_html = generate_opits_html(rows_opit, now)
    (REPORTES_DIR / "opits.html").write_text(opits_html, encoding="utf-8")
    print("  [OK] reportes/opits.html")

    print("Parcheando nav en HTMLs existentes...")
    nav_patches = [
        (NAV_TV_DISABLED, NAV_TV_ENABLED),
        (BTN_TV_DISABLED, BTN_TV_ENABLED),
        (FOOTER_TV_PROX,  FOOTER_TV_OK),
    ]
    for fname in ["global.html", "fijo.html"]:
        fpath = REPORTES_DIR / fname
        patch_nav(fpath, nav_patches)
        # Añadir link OPITs al nav si no existe
        content = fpath.read_text(encoding="utf-8") if fpath.exists() else ""
        if "opits.html" not in content and '<li><a href="tv.html">' in content:
            content = content.replace(
                '<li><a href="tv.html">TV</a></li>',
                '<li><a href="tv.html">TV</a></li>\n      ' + NAV_OPITs_ENTRY
            )
            fpath.write_text(content, encoding="utf-8")
            print(f"  [OK] Link OPITs añadido a {fname}")

    print("\nListo. Archivos generados:")
    print(f"  reportes/tv.html")
    print(f"  reportes/opits.html")
    print(f"  reportes/global.html  (nav actualizado)")
    print(f"  reportes/fijo.html    (nav actualizado)")


# ─────────────────────────────────────────────────────────────────
# TEMPLATES HTML
# ─────────────────────────────────────────────────────────────────
TV_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Informe SLA TV &mdash; {fecha_str} &mdash; MasOrange</title>
  <style>
    :root {{
      --mo-orange:#FF5900; --mo-black:#000; --mo-white:#fff;
      --mo-gray-light:#F2F2F2; --mo-muted:#666; --mo-border:#e0e0e0;
      --text-main:#111; --text-muted:#666; --bg-strip:#fafafa;
      --nav-h:56px; --mo-margin:clamp(1.5rem,4vw,4rem);
    }}
    [data-theme="dark"] {{
      --mo-white:#111; --mo-gray-light:#1a1a1a; --text-main:#f0f0f0;
      --text-muted:#aaa; --mo-border:#333; --bg-strip:#1c1c1c;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:Arial,Helvetica,sans-serif; background:var(--mo-gray-light); color:var(--text-main); }}
    .mo-nav {{ position:sticky;top:0;z-index:100;background:#000;height:var(--nav-h);
               display:flex;align-items:center;justify-content:space-between;padding:0 24px;gap:16px; }}
    .mo-nav-brand {{ color:#fff;font-weight:700;font-size:.9rem; }}
    .mo-nav-links {{ list-style:none;display:flex;gap:4px; }}
    .mo-nav-links li a {{ color:#ccc;text-decoration:none;font-size:.82rem;font-weight:600;
                          padding:6px 14px;border-radius:4px;transition:background .15s,color .15s; }}
    .mo-nav-links li a:hover {{ background:rgba(255,255,255,.1);color:#fff; }}
    .mo-nav-links li a.active {{ background:var(--mo-orange);color:#fff; }}
    .mo-nav-links li a.disabled {{ color:#555;cursor:not-allowed;pointer-events:none; }}
    .mo-logo {{ width:64px;height:auto;flex-shrink:0; }}
    .mo-theme-btn {{ background:none;border:1px solid #555;color:#ccc;border-radius:4px;
                     padding:5px 10px;font-size:.75rem;cursor:pointer; }}
    .hero {{ background:#000;padding:32px 24px 28px;display:flex;flex-wrap:wrap;
             align-items:center;justify-content:space-between;gap:16px; }}
    .hero-title {{ color:#fff;font-size:1.75rem;font-weight:700; }}
    .hero-sub {{ color:#aaa;font-size:.85rem;margin-top:4px; }}
    .hero-pill {{ padding:6px 16px;border-radius:20px;font-size:.85rem;font-weight:700;
                  color:#fff;background:#E65100; }}
    .kpi-global-block {{ background:var(--mo-white);border-radius:8px;margin:20px 20px 0;
                         padding:20px 24px;display:flex;align-items:center;gap:24px;
                         border-left:5px solid {col_g};box-shadow:0 1px 4px rgba(0,0,0,.06); }}
    .kpi-global-number {{ font-size:2.8rem;font-weight:700;color:{col_g};line-height:1; }}
    .kpi-global-label {{ font-size:.9rem;color:var(--text-muted); }}
    .kpi-global-detail {{ font-size:.8rem;color:var(--text-muted);margin-top:3px; }}
    .cards-grid {{ display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
                   gap:14px;padding:14px 20px; }}
    .kpi-card {{ background:var(--mo-white);border-radius:8px;padding:16px 18px;
                 box-shadow:0 1px 4px rgba(0,0,0,.06); }}
    .kpi-card-header {{ display:flex;justify-content:space-between;align-items:center;margin-bottom:8px; }}
    .kpi-card-label {{ font-weight:700;font-size:.85rem; }}
    .kpi-card-sla {{ font-size:.72rem;color:var(--text-muted); }}
    .kpi-card-pct {{ font-size:1.9rem;font-weight:700;line-height:1;margin-bottom:10px; }}
    .kpi-bar-bg {{ background:#f0f0f0;border-radius:3px;height:8px;overflow:hidden;margin-bottom:8px; }}
    .kpi-bar-fill {{ height:8px;border-radius:3px; }}
    .kpi-card-detail {{ font-size:.75rem;color:var(--text-muted); }}
    .tabla-seccion {{ padding:20px 20px 0; }}
    .seccion-header {{ display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap; }}
    .seccion-header h2 {{ font-size:1.1rem;font-weight:700; }}
    .mo-badge {{ padding:3px 10px;border-radius:12px;font-size:.75rem;font-weight:700;color:#fff; }}
    .mo-badge-gray {{ background:#e0e0e0;color:#333; }}
    .tabla-toolbar {{ display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px; }}
    .tabla-filter-input {{ border:1px solid var(--mo-border);border-radius:4px;padding:5px 10px;
                           font-size:.8rem;background:var(--mo-white);color:var(--text-main);width:200px; }}
    .tabla-filter-btn {{ border:1px solid var(--mo-border);background:var(--mo-white);
                         color:var(--text-main);border-radius:4px;padding:5px 12px;font-size:.8rem;cursor:pointer; }}
    .tabla-filter-btn.active {{ background:var(--mo-orange);color:#fff;border-color:var(--mo-orange); }}
    .tabla-count {{ font-size:.78rem;color:var(--text-muted);margin-left:4px; }}
    .btn-export-csv {{ border:1px solid var(--mo-border);background:var(--mo-white);
                       color:var(--text-main);border-radius:4px;padding:5px 12px;font-size:.8rem;
                       cursor:pointer;margin-left:auto; }}
    .tabla-wrap {{ overflow-x:auto;margin-bottom:.5rem; }}
    .mo-table {{ width:100%;border-collapse:collapse;font-size:.875rem; }}
    .mo-table th {{ background:#000;color:#fff;padding:.7rem 1rem;text-align:left;font-size:.8rem; }}
    .mo-table td {{ padding:.65rem 1rem;border-bottom:1px solid var(--mo-border);color:var(--text-main); }}
    .mo-table tr:nth-child(even) td {{ background:var(--bg-strip); }}
    .mo-table tr:hover td {{ background:rgba(255,89,0,.08); }}
    .mo-table a {{ color:var(--mo-orange);text-decoration:none; }}
    .mo-table a:hover {{ text-decoration:underline; }}
    .row-critico td {{ background:rgba(198,40,40,.07) !important; }}
    .toggle-row {{ cursor:pointer; }}
    .toggle-cell {{ text-align:center;font-size:.8rem;color:var(--mo-orange);
                    padding:.7rem;font-weight:700;background:rgba(255,89,0,.04); }}
    .toggle-row:hover .toggle-cell {{ background:rgba(255,89,0,.1); }}
    .mo-footer {{ background:#000;color:#fff;padding:20px 24px;display:flex;
                  justify-content:space-between;align-items:center;flex-wrap:wrap;
                  gap:12px;margin-top:32px;font-size:.8rem; }}
    .mo-footer-links {{ display:flex;gap:16px; }}
    .mo-footer-links a {{ color:#aaa;text-decoration:none; }}
    .mo-footer-links a:hover {{ color:#fff; }}
  </style>
</head>
<body>
<nav class="mo-nav">
  <div style="display:flex;align-items:center;gap:20px">
    <span class="mo-nav-brand">BOST &middot; SLA Dashboard</span>
    <ul class="mo-nav-links">
      <li><a href="global.html">Global</a></li>
      <li><a href="fijo.html">Fijo</a></li>
      <li><a href="tv.html" class="active">TV</a></li>
      <li><a href="opits.html">OPITs</a></li>
    </ul>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <button class="mo-theme-btn" id="mo-theme-btn">☽ Modo oscuro</button>
    <svg class="mo-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68">
      <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
      <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="#fff" stroke-width="10"/>
    </svg>
  </div>
</nav>

<section class="hero">
  <div>
    <div class="hero-title">SLA TV</div>
    <div class="hero-sub">Tickets sin gesti&oacute;n bajo responsabilidad SAT2 &middot; {fecha_str}</div>
  </div>
  <div class="hero-pill">⚠️ VALIDACIÓN</div>
</section>

<div class="kpi-global-block">
  <div class="kpi-global-number">{total_inc}</div>
  <div>
    <div class="kpi-global-label">tickets INCUMPLE de {total_comp} computables &nbsp;<span style="font-size:1.4rem;font-weight:700;color:{col_g}">{pct_g}% cumplimiento</span></div>
    <div class="kpi-global-detail">Responsabilidad activa SAT2 &middot; TV (SATN2-ZL + Log&iacute;stica) &middot; SLA 24h</div>
  </div>
</div>

<div class="cards-grid">
  <div class="kpi-card" style="border-top:4px solid {col_b}">
    <div class="kpi-card-header">
      <span class="kpi-card-label">SATN2-ZL</span>
      <span class="kpi-card-sla">SLA 24h</span>
    </div>
    <div class="kpi-card-pct" style="color:{col_b}">{pct_b}%</div>
    <div class="kpi-bar-bg"><div class="kpi-bar-fill" style="background:{col_b};width:{pct_b}%"></div></div>
    <div class="kpi-card-detail">{inc_b} incumplen &middot; {tot_b} computables &middot; {excl_b} excluidos FSM</div>
  </div>
  <div class="kpi-card" style="border-top:4px solid {col_l}">
    <div class="kpi-card-header">
      <span class="kpi-card-label">Log&iacute;stica TV</span>
      <span class="kpi-card-sla">SLA 24h</span>
    </div>
    <div class="kpi-card-pct" style="color:{col_l}">{pct_l}%</div>
    <div class="kpi-bar-bg"><div class="kpi-bar-fill" style="background:{col_l};width:{pct_l}%"></div></div>
    <div class="kpi-card-detail">{inc_l} incumplen &middot; {tot_l} computables &middot; {excl_l} excluidos</div>
  </div>
</div>

<!-- SATN2-ZL -->
<section class="tabla-seccion" id="sec-tv_base">
  <div class="seccion-header">
    <h2>SATN2-ZL &mdash; TV</h2>
    <span class="mo-badge" style="background:{col_b};color:#fff">{inc_b} INCUMPLE</span>
    <span class="mo-badge mo-badge-gray">{tot_b} computables &middot; SLA 24h</span>
  </div>
  <div class="tabla-toolbar">
    <input type="text" placeholder="Filtrar marca / motivo…" class="tabla-filter-input" data-sec="tv_base"/>
    <button class="tabla-filter-btn active" data-sec="tv_base" data-filter="all">Todos</button>
    <button class="tabla-filter-btn" data-sec="tv_base" data-filter="critico">Solo &gt;96h</button>
    <span class="tabla-count" id="count-tv_base">{inc_b} INCUMPLE visibles</span>
    <button class="btn-export-csv" data-sec="tv_base">&#8615; CSV</button>
  </div>
  <div class="tabla-wrap">
    <table class="mo-table" id="tabla-tv_base">
      <thead><tr>
        <th>Ticket</th><th>Subcategor&iacute;a</th>
        <th>Horas sin gesti&oacute;n</th><th>&Uacute;ltima gesti&oacute;n</th><th>Estado</th>
      </tr></thead>
      <tbody>{rows_base}</tbody>
    </table>
  </div>
</section>

<!-- LOGÍSTICA TV -->
<section class="tabla-seccion" id="sec-tv_log" style="margin-bottom:32px">
  <div class="seccion-header">
    <h2>Log&iacute;stica TV</h2>
    <span class="mo-badge" style="background:{col_l};color:#fff">{inc_l} INCUMPLE</span>
    <span class="mo-badge mo-badge-gray">{tot_l} computables &middot; SLA 24h</span>
  </div>
  <div class="tabla-toolbar">
    <input type="text" placeholder="Filtrar marca…" class="tabla-filter-input" data-sec="tv_log"/>
    <button class="tabla-filter-btn active" data-sec="tv_log" data-filter="all">Todos</button>
    <button class="tabla-filter-btn" data-sec="tv_log" data-filter="critico">Solo &gt;96h</button>
    <span class="tabla-count" id="count-tv_log">{inc_l} INCUMPLE visibles</span>
    <button class="btn-export-csv" data-sec="tv_log">&#8615; CSV</button>
  </div>
  <div class="tabla-wrap">
    <table class="mo-table" id="tabla-tv_log">
      <thead><tr>
        <th>Ticket</th><th>Subcategor&iacute;a</th>
        <th>Horas sin gesti&oacute;n</th><th>&Uacute;ltima gesti&oacute;n</th><th>Estado</th>
      </tr></thead>
      <tbody>{rows_log}</tbody>
    </table>
  </div>
</section>

<footer class="mo-footer">
  <div>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" width="48" aria-label="MasOrange">
      <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
      <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="#fff" stroke-width="10"/>
    </svg>
    <span style="margin-left:10px">Generado autom&aacute;ticamente &middot; BOST MasOrange &middot; {fecha_str} {hora_str}h</span>
  </div>
  <div class="mo-footer-links">
    <a href="global.html">Global</a>
    <a href="fijo.html">Informe Fijo</a>
    <a href="opits.html">OPITs</a>
  </div>
</footer>

<script>
(function() {{
  var btn = document.getElementById('mo-theme-btn');
  var html = document.documentElement;
  var dark = localStorage.getItem('mo-theme') === 'dark' ||
    (!localStorage.getItem('mo-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
  function apply(d) {{
    html.setAttribute('data-theme', d ? 'dark' : 'light');
    btn.textContent = d ? '☀ Modo claro' : '☽ Modo oscuro';
    localStorage.setItem('mo-theme', d ? 'dark' : 'light');
  }}
  apply(dark);
  btn.addEventListener('click', function() {{ dark = !dark; apply(dark); }});
}})();

// Toggle filas colapsadas
document.querySelectorAll('.toggle-row').forEach(function(tr) {{
  tr.addEventListener('click', function() {{
    var sec = tr.getAttribute('data-sec');
    var hidden = document.querySelectorAll('.otros-row-' + sec);
    var cell = tr.querySelector('.toggle-cell');
    var showing = hidden[0] && hidden[0].style.display !== 'none';
    hidden.forEach(function(r) {{ r.style.display = showing ? 'none' : ''; }});
    cell.textContent = showing
      ? '▼ Ver ' + hidden.length + ' tickets dentro de SLA / excluidos'
      : '▲ Ocultar tickets dentro de SLA / excluidos';
  }});
}});

// Filtros
document.querySelectorAll('.tabla-filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    var sec = btn.getAttribute('data-sec');
    var filter = btn.getAttribute('data-filter');
    document.querySelectorAll('[data-sec="' + sec + '"].tabla-filter-btn')
      .forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    var tbl = document.getElementById('tabla-' + sec);
    var cnt = 0;
    tbl.querySelectorAll('tbody tr').forEach(function(tr) {{
      if (tr.classList.contains('toggle-row')) return;
      var horas = parseFloat(tr.getAttribute('data-horas'));
      var show = filter === 'all' || (filter === 'critico' && horas > 96);
      tr.style.display = show ? '' : 'none';
      if (show && !tr.classList.contains('toggle-row') && !tr.className.includes('otros-row')) cnt++;
    }});
    document.getElementById('count-' + sec).textContent = cnt + ' INCUMPLE visibles';
  }});
}});

// Filtro texto
document.querySelectorAll('.tabla-filter-input').forEach(function(inp) {{
  inp.addEventListener('input', function() {{
    var sec = inp.getAttribute('data-sec');
    var q = inp.value.toLowerCase();
    document.getElementById('tabla-' + sec).querySelectorAll('tbody tr').forEach(function(tr) {{
      if (tr.classList.contains('toggle-row')) return;
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
}});

// CSV export
document.querySelectorAll('.btn-export-csv').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    var sec = btn.getAttribute('data-sec');
    var tbl = document.getElementById('tabla-' + sec);
    var rows = [Array.from(tbl.querySelectorAll('thead th')).map(function(th) {{ return th.textContent; }})];
    tbl.querySelectorAll('tbody tr:not([style*="display: none"])').forEach(function(tr) {{
      if (tr.classList.contains('toggle-row')) return;
      rows.push(Array.from(tr.querySelectorAll('td')).map(function(td) {{ return td.textContent.trim(); }}));
    }});
    var csv = rows.map(function(r) {{ return r.map(function(c) {{ return '"' + c.replace(/"/g,'""') + '"'; }}).join(','); }}).join('\\n');
    var a = document.createElement('a');
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = 'tv_' + sec + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }});
}});
</script>
</body>
</html>
"""

OPITS_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OPITs Activos &mdash; {fecha_str} &mdash; MasOrange</title>
  <style>
    :root {{
      --mo-orange:#FF5900; --mo-black:#000; --mo-white:#fff;
      --mo-gray-light:#F2F2F2; --text-main:#111; --text-muted:#666;
      --mo-border:#e0e0e0; --bg-strip:#fafafa; --nav-h:56px;
    }}
    [data-theme="dark"] {{
      --mo-white:#111; --mo-gray-light:#1a1a1a; --text-main:#f0f0f0;
      --text-muted:#aaa; --mo-border:#333; --bg-strip:#1c1c1c;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:Arial,Helvetica,sans-serif; background:var(--mo-gray-light); color:var(--text-main); }}
    .mo-nav {{ position:sticky;top:0;z-index:100;background:#000;height:var(--nav-h);
               display:flex;align-items:center;justify-content:space-between;padding:0 24px;gap:16px; }}
    .mo-nav-brand {{ color:#fff;font-weight:700;font-size:.9rem; }}
    .mo-nav-links {{ list-style:none;display:flex;gap:4px; }}
    .mo-nav-links li a {{ color:#ccc;text-decoration:none;font-size:.82rem;font-weight:600;
                          padding:6px 14px;border-radius:4px;transition:background .15s; }}
    .mo-nav-links li a:hover {{ background:rgba(255,255,255,.1);color:#fff; }}
    .mo-nav-links li a.active {{ background:var(--mo-orange);color:#fff; }}
    .mo-logo {{ width:64px;height:auto;flex-shrink:0; }}
    .mo-theme-btn {{ background:none;border:1px solid #555;color:#ccc;border-radius:4px;
                     padding:5px 10px;font-size:.75rem;cursor:pointer; }}
    .hero {{ background:#000;padding:32px 24px 28px; }}
    .hero-title {{ color:#fff;font-size:1.75rem;font-weight:700; }}
    .hero-sub {{ color:#aaa;font-size:.85rem;margin-top:4px; }}
    .summary-block {{ background:var(--mo-white);border-radius:8px;margin:20px 20px 0;
                      padding:16px 24px;display:flex;gap:32px;flex-wrap:wrap;
                      border-left:5px solid var(--mo-orange);box-shadow:0 1px 4px rgba(0,0,0,.06); }}
    .sum-item {{ display:flex;flex-direction:column; }}
    .sum-num {{ font-size:2rem;font-weight:700; }}
    .sum-label {{ font-size:.8rem;color:var(--text-muted);margin-top:2px; }}
    .tab-bar {{ display:flex;gap:8px;padding:16px 20px 0; }}
    .tab-btn {{ padding:8px 20px;border-radius:6px 6px 0 0;border:none;font-weight:700;
                font-size:.85rem;cursor:pointer;background:var(--mo-white);color:var(--text-muted); }}
    .tab-btn.active {{ background:var(--mo-orange);color:#fff; }}
    .tab-panel {{ display:none;padding:0 20px 32px; }}
    .tab-panel.active {{ display:block; }}
    .tabla-wrap {{ overflow-x:auto;margin-top:12px; }}
    .mo-table {{ width:100%;border-collapse:collapse;font-size:.875rem; }}
    .mo-table th {{ background:#000;color:#fff;padding:.7rem 1rem;text-align:left;font-size:.8rem; }}
    .mo-table td {{ padding:.65rem 1rem;border-bottom:1px solid var(--mo-border); }}
    .mo-table tr:nth-child(even) td {{ background:var(--bg-strip); }}
    .mo-table tr:hover td {{ background:rgba(255,89,0,.08); }}
    .mo-table a {{ color:var(--mo-orange);text-decoration:none; }}
    .row-critico td {{ background:rgba(198,40,40,.07) !important; }}
    .legend {{ font-size:.78rem;color:var(--text-muted);margin-top:10px; }}
    .mo-footer {{ background:#000;color:#fff;padding:20px 24px;display:flex;
                  justify-content:space-between;align-items:center;flex-wrap:wrap;
                  gap:12px;margin-top:32px;font-size:.8rem; }}
    .mo-footer a {{ color:#aaa;text-decoration:none; }}
  </style>
</head>
<body>
<nav class="mo-nav">
  <div style="display:flex;align-items:center;gap:20px">
    <span class="mo-nav-brand">BOST &middot; SLA Dashboard</span>
    <ul class="mo-nav-links">
      <li><a href="global.html">Global</a></li>
      <li><a href="fijo.html">Fijo</a></li>
      <li><a href="tv.html">TV</a></li>
      <li><a href="opits.html" class="active">OPITs</a></li>
    </ul>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <button class="mo-theme-btn" id="mo-theme-btn">☽ Modo oscuro</button>
    <svg class="mo-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68">
      <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
      <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="#fff" stroke-width="10"/>
    </svg>
  </div>
</nav>

<section class="hero">
  <div class="hero-title">OPITs Activos</div>
  <div class="hero-sub">Solo OPITs abiertos &middot; {dia_str}, {fecha_str} &middot; Generado {hora_str}h</div>
</section>

<div class="summary-block">
  <div class="sum-item" style="border-right:1px solid var(--mo-border);padding-right:28px;margin-right:4px">
    <span class="sum-num">{total_all}</span>
    <span class="sum-label">OPITs abiertos</span>
  </div>
  <div class="sum-item">
    <span class="sum-num" style="color:#1565C0">{total_tv}</span>
    <span class="sum-label">TV &nbsp;<span style="font-size:.78rem;font-weight:400;color:#C62828">🔴 {criticos_tv}</span> <span style="font-size:.78rem;font-weight:400;color:#E65100">🟡 {avisos_tv}</span></span>
  </div>
  <div class="sum-item">
    <span class="sum-num" style="color:#FF5900">{total_fijo}</span>
    <span class="sum-label">Fijo &nbsp;<span style="font-size:.78rem;font-weight:400;color:#C62828">🔴 {criticos_fijo}</span> <span style="font-size:.78rem;font-weight:400;color:#E65100">🟡 {avisos_fijo}</span></span>
  </div>
</div>

<div class="tab-bar">
  <button class="tab-btn active" data-tab="tv">TV ({total_tv})</button>
  <button class="tab-btn" data-tab="fijo">Fijo ({total_fijo})</button>
</div>

<div id="panel-tv" class="tab-panel active">
  <div class="tabla-wrap">
    <table class="mo-table">
      <thead><tr>
        <th>Ticket</th><th>Marca</th><th>OPIT</th><th>Estado OPIT</th>
        <th>Prioridad</th><th>D&iacute;as abierto</th><th>Alerta</th><th>Resumen</th>
      </tr></thead>
      <tbody>{rows_tv}</tbody>
    </table>
  </div>
  <div class="legend">🔴 &gt;10 d&iacute;as &middot; 🟡 &gt;5 d&iacute;as &middot; 🟢 OK &middot; Los tickets siguen computando en SLA normal</div>
</div>

<div id="panel-fijo" class="tab-panel">
  <div class="tabla-wrap">
    <table class="mo-table">
      <thead><tr>
        <th>Ticket</th><th>Marca</th><th>OPIT</th><th>Estado OPIT</th>
        <th>Prioridad</th><th>D&iacute;as abierto</th><th>Alerta</th><th>Resumen</th>
      </tr></thead>
      <tbody>{rows_fijo}</tbody>
    </table>
  </div>
  <div class="legend">🔴 &gt;10 d&iacute;as &middot; 🟡 &gt;5 d&iacute;as &middot; 🟢 OK &middot; Los tickets siguen computando en SLA normal</div>
</div>

<footer class="mo-footer">
  <span>Generado autom&aacute;ticamente &middot; BOST MasOrange &middot; {fecha_str} {hora_str}h</span>
  <div style="display:flex;gap:16px">
    <a href="global.html">Global</a>
    <a href="fijo.html">Fijo</a>
    <a href="tv.html">TV</a>
  </div>
</footer>

<script>
(function() {{
  var btn = document.getElementById('mo-theme-btn');
  var html = document.documentElement;
  var dark = localStorage.getItem('mo-theme') === 'dark' ||
    (!localStorage.getItem('mo-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
  function apply(d) {{
    html.setAttribute('data-theme', d ? 'dark' : 'light');
    btn.textContent = d ? '☀ Modo claro' : '☽ Modo oscuro';
    localStorage.setItem('mo-theme', d ? 'dark' : 'light');
  }}
  apply(dark);
  btn.addEventListener('click', function() {{ dark = !dark; apply(dark); }});
}})();

document.querySelectorAll('.tab-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    var tab = btn.getAttribute('data-tab');
    document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    document.querySelectorAll('.tab-panel').forEach(function(p) {{ p.classList.remove('active'); }});
    btn.classList.add('active');
    document.getElementById('panel-' + tab).classList.add('active');
  }});
}});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
