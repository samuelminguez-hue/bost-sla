#!/usr/bin/env python3
"""
Genera tv.html y opits.html con datos del día y habilita los links en el nav.
Uso standalone — no modifica informe_sla_fijo.py ni el flujo de Fijo.
Épica: BST-13120 | BST-13293 / BST-13294 / BST-13295
"""

import re
import sys
import pathlib
import urllib.request
import urllib.error
import json as _json
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

from google.cloud import bigquery

PROJECT_ID   = "mm-datamart-kd"
SCRIPT_DIR   = Path(__file__).parent
REPORTES_DIR = SCRIPT_DIR / "reportes"
TZ           = ZoneInfo("Europe/Madrid")

# ─────────────────────────────────────────────────────────────────
# JIRA ENRICHMENT — rellena PRIO_OPIT y FECHA_CREACION_OPIT para
# filas donde BQ no tiene esos datos (prefijos MYS-, TTV-, etc.)
# ─────────────────────────────────────────────────────────────────
def _jira_pat():
    try:
        sh = pathlib.Path.home() / ".claude" / "jira-personal.sh"
        m = re.search(r'JIRA_PAT_SAMUEL="([^"]+)"', sh.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except Exception:
        return ""


def enriquecer_opits_jira(rows):
    """Para filas con PRIO_OPIT o FECHA_CREACION_OPIT nulos, consulta Jira API."""
    pat = _jira_pat()
    if not pat:
        return rows

    pendientes = [r for r in rows if r.get("PRIO_OPIT") is None or r.get("FECHA_CREACION_OPIT") is None]
    if not pendientes:
        return rows

    print(f"  [Jira] Enriqueciendo {len(pendientes)} OPITs sin datos en BQ...")
    base = "https://jiranext.masorange.es/rest/api/2/issue"
    headers = {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"}

    for r in pendientes:
        opit_key = r.get("opit_clave") or r.get("ISSUE_OPIT") or r.get("REMOTE_LINK_OPIT")
        if not opit_key:
            continue
        try:
            req = urllib.request.Request(
                f"{base}/{opit_key}?fields=priority,created",
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read())
            fields = data.get("fields", {})
            if r.get("PRIO_OPIT") is None:
                r["PRIO_OPIT"] = (fields.get("priority") or {}).get("name")
            if r.get("FECHA_CREACION_OPIT") is None and fields.get("created"):
                created_str = fields["created"][:10]  # "YYYY-MM-DD"
                r["FECHA_CREACION_OPIT"] = datetime.strptime(created_str, "%Y-%m-%d")
                today = datetime.now(tz=ZoneInfo("Europe/Madrid")).date()
                dias = (today - r["FECHA_CREACION_OPIT"].date()).days
                r["dias_opit_abierto"] = dias
                r["alerta_opit"] = "CRITICO" if dias > 10 else ("AVISO" if dias > 5 else "OK")
            print(f"    {opit_key}: prio={r['PRIO_OPIT']} dias={r.get('dias_opit_abierto')}")
        except Exception as e:
            print(f"    [WARN] {opit_key}: {e}")

    return rows


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
    return "#2E7D32" if pct >= 80 else "#C62828"

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
            # fallback a fecha_inicio_reloj si no hay gestión registrada
            ult_gestion = fmt_date(r.get("fecha_ultima_gestion") or r.get("fecha_inicio_reloj"))
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
        opit   = esc(r.get("opit_clave") or r.get("ISSUE_OPIT"))
        status = esc(r.get("opit_status") or r.get("OPIT_STATUS"))
        prio   = esc(r.get("PRIO_OPIT"))
        dias_raw = r.get("dias_opit_abierto")
        dias_display = f"{dias_raw}d" if dias_raw is not None else "—"
        alerta = r.get("alerta_opit", "OK")
        icon   = alerta_icon(alerta)
        resumen = esc(r.get("opit_summary") or r.get("OPIT_SUMMARY"))
        fila_cls = ' class="row-critico"' if alerta == "CRITICO" else ""
        html += (
            f'<tr{fila_cls}>'
            f'<td><a href="https://tgjira.masmovil.com/browse/{clave}" target="_blank">{clave}</a></td>'
            f'<td>{marca}</td>'
            f'<td><a href="https://jiranext.masmovil.com/browse/{opit}" target="_blank">{opit}</a></td>'
            f'<td>{status}</td>'
            f'<td>{prio}</td>'
            f'<td style="font-weight:700">{dias_display}</td>'
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
# SECCIÓN OPITs PARA GLOBAL.HTML
# Agrupada por OPIT (entidad principal), ordenada por más antiguo primero
# ─────────────────────────────────────────────────────────────────
OPIT_GLOBAL_CSS = """
    /* OPITS SECTION */
    .opit-section { background:var(--mo-white); border-radius:8px; margin:0 20px 14px; padding:20px 24px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
    .opit-header { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
    .opit-header h2 { font-size:1rem; font-weight:700; }
    .opit-badge { padding:3px 10px; border-radius:12px; font-size:.72rem; font-weight:700; background:#000; color:#fff; }
    .opit-table { width:100%; border-collapse:collapse; font-size:.82rem; }
    .opit-table th { background:#000; color:#fff; padding:.6rem .8rem; text-align:left; font-size:.75rem; }
    .opit-table td { padding:.55rem .8rem; border-bottom:1px solid var(--mo-border); vertical-align:middle; }
    .opit-table tr.opit-row:hover td { background:rgba(255,89,0,.06); cursor:pointer; }
    .opit-table a { color:var(--mo-orange); text-decoration:none; }
    .opit-table a:hover { text-decoration:underline; }
    .opit-row-critico td { background:rgba(198,40,40,.05) !important; }
    .opit-row-aviso td { background:rgba(255,160,0,.05) !important; }
    .opit-tickets-row { display:none; }
    .opit-tickets-row td { padding:.4rem .8rem .8rem 2.5rem; background:var(--mo-gray) !important; }
    .opit-tickets-list { display:flex; flex-wrap:wrap; gap:4px 6px; margin-top:4px; }
    .opit-ticket-chip { font-size:.72rem; padding:2px 8px; border-radius:3px; background:var(--mo-white); border:1px solid var(--mo-border); color:var(--mo-text); text-decoration:none; }
    .opit-ticket-chip:hover { border-color:var(--mo-orange); color:var(--mo-orange); }
    .opit-expand-icon { font-size:.7rem; color:var(--mo-orange); transition:transform .2s; display:inline-block; }
    .opit-row.open .opit-expand-icon { transform:rotate(90deg); }
    .opit-resumen { max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:.78rem; color:var(--mo-muted); }
"""

OPIT_GLOBAL_JS = """
function toggleOpit(row) {
  var id = row.dataset.id;
  var detailRow = document.getElementById(id);
  var icon = row.querySelector('.opit-expand-icon');
  var open = detailRow.style.display === 'table-row';
  detailRow.style.display = open ? 'none' : 'table-row';
  row.classList.toggle('open', !open);
}
"""

def _dias_color(dias):
    if dias is None:
        return "var(--mo-muted)"
    if dias > 10:
        return "#C62828"
    if dias > 5:
        return "#E65100"
    return "var(--mo-text)"


def build_opit_global_section(rows_all):
    """Genera el bloque HTML de OPITs para global.html, agrupado por OPIT."""
    from collections import defaultdict

    ALERTA_RANK = {"CRITICO": 3, "AVISO": 2, "OK": 1, "SIN_FECHA": 0}
    grupos = {}  # opit_clave -> dict

    for r in rows_all:
        opit_key = r.get("opit_clave") or r.get("ISSUE_OPIT") or ""
        if not opit_key:
            continue
        if opit_key not in grupos:
            grupos[opit_key] = {
                "tickets": [],
                "opit_summary":   r.get("opit_summary") or r.get("OPIT_SUMMARY"),
                "opit_status":    r.get("opit_status")  or r.get("OPIT_STATUS"),
                "PRIO_OPIT":      r.get("PRIO_OPIT"),
                "dias":           r.get("dias_opit_abierto"),
                "alerta":         r.get("alerta_opit", "OK"),
                "tipo":           set(),
            }
        g = grupos[opit_key]
        g["tickets"].append(r.get("CLAVE", ""))
        tipo = r.get("TIPO_SERVICIO", "")
        g["tipo"].add("TV" if tipo == "TV" else "Fijo")
        cur_rank  = ALERTA_RANK.get(r.get("alerta_opit", "OK"), 1)
        prev_rank = ALERTA_RANK.get(g["alerta"], 1)
        if cur_rank > prev_rank:
            g["alerta"] = r.get("alerta_opit", "OK")

    if not grupos:
        return ""

    # Ordenar: más días primero (None al final)
    sorted_opits = sorted(
        grupos.items(),
        key=lambda kv: (kv[1]["dias"] is None, -(kv[1]["dias"] or 0))
    )

    total_opits   = len(sorted_opits)
    total_tickets = sum(len(g["tickets"]) for _, g in sorted_opits)

    rows_html = ""
    for idx, (opit_key, g) in enumerate(sorted_opits):
        uid      = f"opit{idx}"
        alerta   = g["alerta"]
        dias     = g["dias"]
        icon     = alerta_icon(alerta)
        row_cls  = "opit-row-critico" if alerta == "CRITICO" else ("opit-row-aviso" if alerta == "AVISO" else "")
        dias_disp = f"{dias}d" if dias is not None else "—"
        dias_color = _dias_color(dias)
        tipo_str = " / ".join(sorted(g["tipo"]))
        resumen  = esc(g["opit_summary"] or "")
        status   = esc(g["opit_status"]  or "—")
        prio     = esc(g["PRIO_OPIT"]    or "—")
        num      = len(g["tickets"])
        opit_esc = esc(opit_key)

        rows_html += (
            f'<tr class="opit-row {row_cls}" onclick="toggleOpit(this)" data-id="{uid}">'
            f'<td><span class="opit-expand-icon">&#9658;</span></td>'
            f'<td><a href="https://jiranext.masmovil.com/browse/{opit_esc}" target="_blank" onclick="event.stopPropagation()">{opit_esc}</a></td>'
            f'<td class="opit-resumen" title="{resumen}">{resumen}</td>'
            f'<td>{status}</td>'
            f'<td>{tipo_str}</td>'
            f'<td>{prio}</td>'
            f'<td><strong style="color:{dias_color}">{dias_disp}</strong></td>'
            f'<td><strong>{num}</strong></td>'
            f'<td>{icon}</td>'
            f'</tr>\n'
        )

        chips = ""
        MAX_SHOW = 25
        shown = g["tickets"][:MAX_SHOW]
        extra = len(g["tickets"]) - MAX_SHOW
        for clave in shown:
            clave_e = esc(clave)
            chips += f'<a class="opit-ticket-chip" href="https://tgjira.masmovil.com/browse/{clave_e}" target="_blank">{clave_e}</a>'
        if extra > 0:
            chips += f'<span style="font-size:.72rem;color:var(--mo-muted)">&hellip; y {extra} m&aacute;s</span>'

        label_t = "ticket asociado" if num == 1 else "tickets asociados"
        rows_html += (
            f'<tr class="opit-tickets-row" id="{uid}">'
            f'<td colspan="9">'
            f'<div style="font-size:.72rem;color:var(--mo-muted);margin-bottom:4px">{num} {label_t}:</div>'
            f'<div class="opit-tickets-list">{chips}</div>'
            f'</td></tr>\n'
        )

    return (
        f'\n<!-- OPITS -->\n'
        f'<div class="opit-section">\n'
        f'  <div class="opit-header">\n'
        f'    <h2>OPITs abiertos</h2>\n'
        f'    <span class="opit-badge">{total_opits} OPITs &middot; {total_tickets} tickets</span>\n'
        f'  </div>\n'
        f'  <div style="overflow-x:auto">\n'
        f'  <table class="opit-table">\n'
        f'    <thead><tr>'
        f'<th style="width:28px"></th><th>OPIT</th><th>Resumen</th>'
        f'<th>Estado</th><th>Tipo</th><th>Prioridad</th><th>D&iacute;as</th><th>Tickets</th><th></th>'
        f'</tr></thead>\n'
        f'    <tbody>\n{rows_html}    </tbody>\n'
        f'  </table>\n'
        f'  </div>\n'
        f'</div>\n'
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
NAV_OPITs_ENTRY    = '<li><a href="opits.html">OPITs</a></li>'
NAV_FEEDBACK_ENTRY = '<li><a href="feedback.html">Feedback</a></li>'

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
    rows_opit = enriquecer_opits_jira(rows_opit)
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
        # Añadir links OPITs y Feedback al nav si no existen
        content = fpath.read_text(encoding="utf-8") if fpath.exists() else ""
        changed = False
        if "opits.html" not in content and '<li><a href="tv.html">' in content:
            content = content.replace(
                '<li><a href="tv.html">TV</a></li>',
                '<li><a href="tv.html">TV</a></li>\n      ' + NAV_OPITs_ENTRY
            )
            changed = True
        if "feedback.html" not in content and "opits.html" in content:
            content = content.replace(
                NAV_OPITs_ENTRY,
                NAV_OPITs_ENTRY + '\n      ' + NAV_FEEDBACK_ENTRY
            )
            changed = True
        if changed:
            fpath.write_text(content, encoding="utf-8")
            print(f"  [OK] Nav actualizado en {fname}")

    # Inyectar sección OPITs en global.html
    global_path = REPORTES_DIR / "global.html"
    if global_path.exists():
        content = global_path.read_text(encoding="utf-8")
        # Inyectar CSS (solo si no está ya)
        if "opit-section" not in content:
            content = content.replace("</style>", OPIT_GLOBAL_CSS + "\n  </style>", 1)
        # Inyectar JS del toggle (solo si no está ya)
        if "toggleOpit" not in content:
            content = content.replace("</body>", f"<script>{OPIT_GLOBAL_JS}</script>\n</body>", 1)
        # Reemplazar placeholder (siempre, para que cada día tenga datos frescos)
        opit_section = build_opit_global_section(rows_opit)
        if "<!-- OPIT_WIDGET_PLACEHOLDER -->" in content:
            content = content.replace("<!-- OPIT_WIDGET_PLACEHOLDER -->", opit_section)
        elif "<!-- OPITS -->" not in content:
            # fallback: inyectar antes del footer si el placeholder no existe
            content = content.replace("<!-- FOOTER -->", opit_section + "\n<!-- FOOTER -->", 1)
        global_path.write_text(content, encoding="utf-8")
        print("  [OK] Sección OPITs inyectada en global.html")

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
      --border-subtle:#e5e5e5; --nav-bg:rgba(255,255,255,0.88);
      --nav-h:56px; --mo-margin:clamp(1.5rem,4vw,4rem);
    }}
    [data-theme="dark"] {{
      --mo-white:#111; --mo-gray-light:#1a1a1a; --text-main:#f0f0f0;
      --text-muted:#aaa; --mo-border:#333; --bg-strip:#1c1c1c;
      --border-subtle:#2a2a2a; --nav-bg:rgba(13,13,13,0.88);
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:'Outfit',Arial,Helvetica,sans-serif; background:var(--mo-gray-light); color:var(--text-main); }}
    .mo-nav {{
      position:sticky; top:0; z-index:100;
      display:flex; align-items:center; justify-content:space-between;
      padding:0 var(--mo-margin); height:var(--nav-h);
      background:var(--nav-bg); border-bottom:1px solid var(--border-subtle);
      backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
    }}
    .mo-nav-brand {{ font-size:0.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);white-space:nowrap; }}
    .mo-nav-links {{ list-style:none;display:flex;gap:0;height:var(--nav-h);margin:0;padding:0; }}
    .mo-nav-links li {{ display:flex; }}
    .mo-nav-links li a {{ display:flex;align-items:center;height:100%;padding:0 1.1rem;font-size:0.875rem;color:var(--text-muted);
                          border-bottom:3px solid transparent;text-decoration:none;transition:color .15s,border-color .15s; }}
    .mo-nav-links li a:hover {{ color:var(--text-main); }}
    .mo-nav-links li a.active {{ color:var(--text-main);font-weight:700;border-bottom-color:var(--mo-orange); }}
    .mo-nav-links li a.disabled {{ color:var(--border-subtle);cursor:default;pointer-events:none; }}
    .mo-logo {{ width:64px;height:auto;flex-shrink:0; }}
    .mo-theme-btn {{ background:none;border:1.5px solid var(--border-subtle);border-radius:20px;
                     padding:0.3rem 0.8rem;cursor:pointer;font-size:0.8rem;color:var(--text-main);
                     display:flex;align-items:center;gap:0.4rem;transition:border-color .2s,color .2s; }}
    .mo-theme-btn:hover {{ border-color:var(--mo-orange);color:var(--mo-orange); }}
    .hero {{ background:#000; color:#fff; padding:2.5rem var(--mo-margin) 2rem; }}
    .hero-title {{ color:#fff;font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;margin-bottom:0.5rem; }}
    .hero-sub {{ color:#ccc;font-size:1rem;margin-bottom:1rem; }}
    .hero-pill {{ display:inline-block;padding:6px 16px;border-radius:20px;font-size:.85rem;font-weight:700;
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
    .kpi-label   {{ font-size:.78rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.03em;margin-bottom:.4rem; }}
    .kpi-incumple{{ font-size:2.8rem;font-weight:700;line-height:1;margin-bottom:.2rem;font-variant-numeric:tabular-nums;font-feature-settings:"tnum"; }}
    .kpi-sub     {{ font-size:.8rem;color:var(--text-muted);margin-bottom:.2rem; }}
    .kpi-pct     {{ font-size:.95rem;font-weight:700; }}
    .kpi-bar     {{ height:3px;background:var(--border-subtle,#e0e0e0);border-radius:2px;margin-top:8px;overflow:hidden; }}
    .kpi-bar-fill{{ height:3px;border-radius:3px; }}
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
    /* ══ REDESIGN VISUAL ══════════════════════════════════════════ */
    html {{ scroll-behavior:smooth; }}
    @keyframes fadeUp {{
      from {{ opacity:0; transform:translateY(12px); }}
      to   {{ opacity:1; transform:translateY(0); }}
    }}
    .kpi-card {{
      transition:transform 200ms cubic-bezier(0.4,0,0.2,1), box-shadow 200ms;
      animation:fadeUp 0.35s ease forwards;
      animation-delay:calc(var(--i,0) * 70ms); opacity:0;
    }}
    .kpi-card:hover {{ transform:translateY(-2px); box-shadow:0 8px 24px rgba(255,89,0,0.12); }}
    .mo-table tbody tr {{ transition:transform 150ms ease; }}
    .mo-table tbody tr:hover td {{ background:rgba(255,89,0,0.06) !important; }}
    .mo-table tbody tr:hover {{ transform:translateX(3px); }}
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
      <li><a href="feedback.html">Feedback</a></li>
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
  <div class="kpi-card" style="--i:0;border-top:4px solid {col_b}">
    <div class="kpi-label">SATN2-ZL &middot; SLA 24h</div>
    <div class="kpi-incumple" style="color:{col_b}">{inc_b}</div>
    <div class="kpi-sub">de {tot_b} computables &middot; {excl_b} excluidos FSM</div>
    <div class="kpi-pct" style="color:{col_b}">{pct_b}% cumplimiento</div>
    <div class="kpi-bar"><div class="kpi-bar-fill" style="width:{pct_b}%;background:{col_b}"></div></div>
  </div>
  <div class="kpi-card" style="--i:1;border-top:4px solid {col_l}">
    <div class="kpi-label">Log&iacute;stica TV &middot; SLA 24h</div>
    <div class="kpi-incumple" style="color:{col_l}">{inc_l}</div>
    <div class="kpi-sub">de {tot_l} computables &middot; {excl_l} excluidos</div>
    <div class="kpi-pct" style="color:{col_l}">{pct_l}% cumplimiento</div>
    <div class="kpi-bar"><div class="kpi-bar-fill" style="width:{pct_l}%;background:{col_l}"></div></div>
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
    <a href="feedback.html">Feedback</a>
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
      --mo-border:#e0e0e0; --bg-strip:#fafafa;
      --border-subtle:#e5e5e5; --nav-bg:rgba(255,255,255,0.88);
      --nav-h:56px; --mo-margin:clamp(1.5rem,4vw,4rem);
    }}
    [data-theme="dark"] {{
      --mo-white:#111; --mo-gray-light:#1a1a1a; --text-main:#f0f0f0;
      --text-muted:#aaa; --mo-border:#333; --bg-strip:#1c1c1c;
      --border-subtle:#2a2a2a; --nav-bg:rgba(13,13,13,0.88);
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:'Outfit',Arial,Helvetica,sans-serif; background:var(--mo-gray-light); color:var(--text-main); }}
    .mo-nav {{
      position:sticky; top:0; z-index:100;
      display:flex; align-items:center; justify-content:space-between;
      padding:0 var(--mo-margin); height:var(--nav-h);
      background:var(--nav-bg); border-bottom:1px solid var(--border-subtle);
      backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
    }}
    .mo-nav-brand {{ font-size:0.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);white-space:nowrap; }}
    .mo-nav-links {{ list-style:none;display:flex;gap:0;height:var(--nav-h);margin:0;padding:0; }}
    .mo-nav-links li {{ display:flex; }}
    .mo-nav-links li a {{ display:flex;align-items:center;height:100%;padding:0 1.1rem;font-size:0.875rem;color:var(--text-muted);
                          border-bottom:3px solid transparent;text-decoration:none;transition:color .15s,border-color .15s; }}
    .mo-nav-links li a:hover {{ color:var(--text-main); }}
    .mo-nav-links li a.active {{ color:var(--text-main);font-weight:700;border-bottom-color:var(--mo-orange); }}
    .mo-logo {{ width:64px;height:auto;flex-shrink:0; }}
    .mo-theme-btn {{ background:none;border:1.5px solid var(--border-subtle);border-radius:20px;
                     padding:0.3rem 0.8rem;cursor:pointer;font-size:0.8rem;color:var(--text-main);
                     display:flex;align-items:center;gap:0.4rem;transition:border-color .2s,color .2s; }}
    .mo-theme-btn:hover {{ border-color:var(--mo-orange);color:var(--mo-orange); }}
    .hero {{ background:#000; color:#fff; padding:2.5rem var(--mo-margin) 2rem; }}
    .hero-title {{ color:#fff;font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;margin-bottom:0.5rem; }}
    .hero-sub {{ color:#ccc;font-size:1rem;margin-bottom:1rem; }}
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
    /* ══ REDESIGN VISUAL ══════════════════════════════════════════ */
    html {{ scroll-behavior:smooth; }}
    @keyframes fadeUp {{
      from {{ opacity:0; transform:translateY(12px); }}
      to   {{ opacity:1; transform:translateY(0); }}
    }}
    .mo-table tbody tr {{ transition:transform 150ms ease; }}
    .mo-table tbody tr:hover td {{ background:rgba(255,89,0,0.06) !important; }}
    .mo-table tbody tr:hover {{ transform:translateX(3px); }}
    .opit-controls {{
      display:flex; align-items:center; gap:10px; flex-wrap:wrap;
      padding:14px 0 6px;
    }}
    .opit-search {{
      flex:1; min-width:200px; max-width:380px;
      padding:7px 12px 7px 34px; border-radius:6px;
      border:1.5px solid var(--mo-border); background:var(--mo-white);
      color:var(--text-main); font-size:.875rem; font-family:inherit;
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");
      background-repeat:no-repeat; background-position:10px center;
      transition:border-color .2s;
    }}
    .opit-search:focus {{ outline:none; border-color:var(--mo-orange); }}
    .opit-select {{
      padding:7px 10px; border-radius:6px;
      border:1.5px solid var(--mo-border); background:var(--mo-white);
      color:var(--text-main); font-size:.8rem; font-family:inherit;
      cursor:pointer; transition:border-color .2s;
    }}
    .opit-select:focus {{ outline:none; border-color:var(--mo-orange); }}
    .opit-count {{ font-size:.78rem; color:var(--text-muted); white-space:nowrap; margin-left:auto; }}
    .opit-group-hdr td {{
      background:var(--mo-border) !important;
      font-size:.75rem; font-weight:700; color:var(--text-muted);
      letter-spacing:.05em; text-transform:uppercase;
      padding:.4rem 1rem !important; border-bottom:none !important;
    }}
    [data-theme="dark"] .opit-group-hdr td {{ background:#2a2a2a !important; }}
  </style>
</head>
<body>
<nav class="mo-nav">
  <div style="display:flex;align-items:center;gap:20px">
    <span class="mo-nav-brand">BOST &middot; SLA Dashboard</span>
    <ul class="mo-nav-links">
      <li><a href="global.html">Global</a></li>
      <li><a href="fijo.html">Fijo + TV</a></li>
      <li><a href="opits.html" class="active">OPITs</a></li>
      <li><a href="feedback.html">Feedback</a></li>
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
  <div class="opit-controls">
    <input type="text" class="opit-search" id="search-tv" placeholder="Buscar ATC, OPIT, marca, resumen…" autocomplete="off">
    <select class="opit-select" id="filter-opit-tv"><option value="">Todos los OPITs</option></select>
    <span class="opit-count" id="count-tv"></span>
  </div>
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
  <div class="opit-controls">
    <input type="text" class="opit-search" id="search-fijo" placeholder="Buscar ATC, OPIT, marca, resumen…" autocomplete="off">
    <select class="opit-select" id="filter-opit-fijo"><option value="">Todos los OPITs</option></select>
    <span class="opit-count" id="count-fijo"></span>
  </div>
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

function setupOPITFilter(panelId, searchId, selectId, countId) {{
  var panel = document.getElementById(panelId);
  if (!panel) return;
  var tbody = panel.querySelector('.mo-table tbody');
  if (!tbody) return;
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var opitMap = {{}};
  rows.forEach(function(tr) {{
    var cells = tr.querySelectorAll('td');
    if (cells.length >= 3) {{
      var opit = cells[2].textContent.trim();
      if (opit && opit !== '—') opitMap[opit] = (opitMap[opit] || 0) + 1;
    }}
  }});
  var sel = document.getElementById(selectId);
  if (sel) {{
    Object.keys(opitMap).sort().forEach(function(o) {{
      var opt = document.createElement('option');
      opt.value = o; opt.textContent = o + ' (' + opitMap[o] + ')';
      sel.appendChild(opt);
    }});
  }}
  var lastOPIT = null;
  rows.forEach(function(tr) {{
    var cells = tr.querySelectorAll('td');
    if (cells.length < 3) return;
    var opit = cells[2].textContent.trim();
    if (opit !== lastOPIT) {{
      var hdr = document.createElement('tr');
      hdr.className = 'opit-group-hdr';
      hdr.dataset.group = opit;
      hdr.innerHTML = '<td colspan="8">' + opit + ' &nbsp;·&nbsp; ' + (opitMap[opit]||0) + ' ticket' + ((opitMap[opit]||0)!==1?'s':'') + '</td>';
      tbody.insertBefore(hdr, tr);
      lastOPIT = opit;
    }}
  }});
  function doFilter() {{
    var q = document.getElementById(searchId).value.toLowerCase().trim();
    var opitFilter = sel ? sel.value : '';
    var visible = 0;
    var dataRows = Array.from(tbody.querySelectorAll('tr:not(.opit-group-hdr)'));
    dataRows.forEach(function(tr) {{
      var text = tr.textContent.toLowerCase();
      var cells = tr.querySelectorAll('td');
      var opit3 = cells.length >= 3 ? cells[2].textContent.trim() : '';
      var show = (!q || text.includes(q)) && (!opitFilter || opit3 === opitFilter);
      tr.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    Array.from(tbody.querySelectorAll('tr.opit-group-hdr')).forEach(function(hdr) {{
      var grp = hdr.dataset.group;
      var hasVisible = Array.from(tbody.querySelectorAll('tr:not(.opit-group-hdr)')).some(function(r) {{
        var cells = r.querySelectorAll('td');
        var opit3 = cells.length >= 3 ? cells[2].textContent.trim() : '';
        return r.style.display !== 'none' && opit3 === grp;
      }});
      hdr.style.display = hasVisible ? '' : 'none';
    }});
    var countEl = document.getElementById(countId);
    if (countEl) countEl.textContent = visible + ' de ' + dataRows.length + ' tickets';
  }}
  document.getElementById(searchId).addEventListener('input', doFilter);
  if (sel) sel.addEventListener('change', doFilter);
  var countEl = document.getElementById(countId);
  if (countEl) countEl.textContent = rows.length + ' tickets';
}}

setupOPITFilter('panel-tv',   'search-tv',   'filter-opit-tv',   'count-tv');
setupOPITFilter('panel-fijo', 'search-fijo', 'filter-opit-fijo', 'count-fijo');
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
