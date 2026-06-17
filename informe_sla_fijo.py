#!/usr/bin/env python3
"""
INFORME SLA FIJO — P5: Generación diaria del informe HTML
Épica: BST-13120 | Ticket: BST-13131

Uso:
    python informe_sla_fijo.py

Output:
    reportes/informe_YYYY-MM-DD.html

Requisitos:
    pip install google-cloud-bigquery
    Credenciales GCP: Application Default Credentials (gcloud auth application-default login)
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.cloud import bigquery

# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────
PROJECT_ID  = "mm-datamart-kd"
SCRIPT_DIR  = Path(__file__).parent
REPORTES_DIR = SCRIPT_DIR / "reportes"

# Destinatarios del email (L-V)
MAIL_TO = "aritz.pajares@masorange.es; joseramon.vigil@masorange.es; samuel.minguez@masorange.es; jaime_rodriguez@masorange.es; guillermo.ibanez@masorange.es; Alfonso.Cobo@masorange.es"

SECCIONES = [
    {
        "key":        "stfijo",
        "label":      "STFIJO-ZL",
        "sla":        "24h",
        "file":       "query_base_p2.sql",
        "col_gestion": "fecha_ultima_gestion",
    },
    {
        "key":        "sgi",
        "label":      "SGI",
        "sla":        "48h",
        "file":       "query_sgi.sql",
        "col_gestion": "fecha_ultima_gestion",
    },
    {
        "key":        "gior",
        "label":      "GIOR",
        "sla":        "24h",
        "file":       "query_gior.sql",
        "col_gestion": "fecha_ultima_gestion",
    },
    {
        "key":        "logistica",
        "label":      "Logística",
        "sla":        "24h",
        "file":       "query_logistica.sql",
        "col_gestion": "fecha_inicio_reloj",
    },
]

# Secciones de visualización: stfijo+sgi+gior unificadas
DISPLAY_SECCIONES = [
    {
        "key":        "fijo",
        "label":      "STFIJO",
        "sla":        "24-48h",
        "keys":       ["stfijo", "sgi", "gior"],
        "col_gestion": "fecha_ultima_gestion",
    },
    {
        "key":        "logistica",
        "label":      "Logística",
        "sla":        "24h",
        "keys":       ["logistica"],
        "col_gestion": "fecha_inicio_reloj",
    },
]

# ─────────────────────────────────────────────────────────────────
# BIGQUERY
# ─────────────────────────────────────────────────────────────────
def run_query(client, sql_path):
    sql = sql_path.read_text(encoding="utf-8")
    job = client.query(sql)
    return [dict(row) for row in job.result()]


# ─────────────────────────────────────────────────────────────────
# HELPERS HTML
# ─────────────────────────────────────────────────────────────────
def kpi_color(pct):
    if pct >= 80:
        return "#2E7D32"   # verde
    elif pct >= 50:
        return "#FF5900"   # naranja MasOrange
    else:
        return "#C62828"   # rojo


def escape_html(value):
    if value is None:
        return "—"
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_rows_html(rows, col_gestion, sec_key):
    """Genera las filas de la tabla: INCUMPLE primero, CUMPLE/EXCLUIDOS colapsados."""
    incumple_rows = [r for r in rows if r.get("estado_sla") == "INCUMPLE"]
    otros_rows    = [r for r in rows if r.get("estado_sla") != "INCUMPLE"]

    html = ""

    for r in incumple_rows:
        clave    = escape_html(r.get("CLAVE"))
        categ    = escape_html(r.get("MOTIVO_SOLICITUD"))
        horas    = r.get("horas_sin_gestion")
        gestion  = escape_html(r.get(col_gestion))
        display  = escape_html(r.get("estado_display"))
        critico_cls = ' class="row-critico"' if horas > 96 else ''
        html += (
            f'<tr{critico_cls} data-horas="{horas}" data-categ="{categ}">'
            f'<td><a href="https://tgjira.masmovil.com/browse/{clave}" target="_blank">{clave}</a></td>'
            f'<td>{categ}</td>'
            f'<td style="font-weight:700;color:#C62828">{horas}h</td>'
            f'<td>{gestion}</td>'
            f'<td>{display}</td>'
            f'</tr>\n'
        )

    if otros_rows:
        html += (
            f'<tr class="toggle-row" data-sec="{sec_key}">'
            f'<td colspan="5" class="toggle-cell">'
            f'▼ Ver {len(otros_rows)} tickets dentro de SLA / excluidos'
            f'</td></tr>\n'
        )
        for r in otros_rows:
            clave   = escape_html(r.get("CLAVE"))
            categ   = escape_html(r.get("MOTIVO_SOLICITUD"))
            horas   = r.get("horas_sin_gestion")
            gestion = escape_html(r.get(col_gestion))
            display = escape_html(r.get("estado_display"))
            html += (
                f'<tr class="otros-row-{sec_key}" data-horas="{horas}" data-categ="{categ}" style="display:none">'
                f'<td><a href="https://tgjira.masmovil.com/browse/{clave}" target="_blank">{clave}</a></td>'
                f'<td>{categ}</td>'
                f'<td>{horas}h</td>'
                f'<td>{gestion}</td>'
                f'<td>{display}</td>'
                f'</tr>\n'
            )

    if not incumple_rows and not otros_rows:
        html = '<tr><td colspan="5" style="text-align:center;color:#999;padding:1.5rem">Sin tickets en esta cola hoy</td></tr>\n'

    return html


# ─────────────────────────────────────────────────────────────────
# GENERACIÓN HTML
# ─────────────────────────────────────────────────────────────────
def generate_html(results, now):
    fecha_str = now.strftime("%d/%m/%Y")
    hora_str  = now.strftime("%H:%M")

    # KPI cards
    kpi_html = ""
    for sec in DISPLAY_SECCIONES:
        key  = sec["key"]
        rows = results[key]

        if key == "logistica":
            computables = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"]
            pct_base    = len(computables)
            total_label = f"{len(rows)} ({pct_base} comput.)"
        else:
            computables = rows
            pct_base    = len(rows)
            total_label = str(len(rows))

        incumple = len([r for r in computables if r.get("estado_sla") == "INCUMPLE"])
        pct      = round(100 * (pct_base - incumple) / pct_base, 1) if pct_base > 0 else 100.0
        color    = kpi_color(pct)

        kpi_html += (
            f'<div class="kpi-card" style="border-top:4px solid {color}">'
            f'<div class="kpi-label">{sec["label"]} · SLA {sec["sla"]}</div>'
            f'<div class="kpi-incumple" style="color:{color}">{incumple}</div>'
            f'<div class="kpi-sub">de {total_label} tickets</div>'
            f'<div class="kpi-pct" style="color:{color}">{pct}% cumplimiento</div>'
            f'</div>\n'
        )

    # Secciones de tabla
    sections_html = ""
    for sec in DISPLAY_SECCIONES:
        key   = sec["key"]
        rows  = results[key]

        if key == "logistica":
            computables = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"]
            pct_base    = len(computables)
            total_label = f"{len(rows)} ({pct_base} comput.)"
        else:
            computables = rows
            pct_base    = len(rows)
            total_label = str(len(rows))

        incumple = len([r for r in computables if r.get("estado_sla") == "INCUMPLE"])
        pct      = round(100 * (pct_base - incumple) / pct_base, 1) if pct_base > 0 else 100.0
        color    = kpi_color(pct)
        rows_html = build_rows_html(rows, sec["col_gestion"], key)

        sections_html += (
            f'<section class="tabla-seccion" id="sec-{key}">'
            f'<div class="seccion-header">'
            f'<h2>{sec["label"]}</h2>'
            f'<span class="mo-badge" style="background:{color};color:#fff">{incumple} INCUMPLE</span>'
            f'<span class="mo-badge mo-badge-gray">{total_label} total · SLA {sec["sla"]}</span>'
            f'</div>'
            f'<div class="tabla-toolbar">'
            f'<input type="text" placeholder="Filtrar subcategoría…" class="tabla-filter-input" data-sec="{key}" />'
            f'<button class="tabla-filter-btn active" data-sec="{key}" data-filter="all">Todos</button>'
            f'<button class="tabla-filter-btn" data-sec="{key}" data-filter="critico">Solo &gt;96h</button>'
            f'<span class="tabla-count" id="count-{key}">{incumple} INCUMPLE visibles</span>'
            f'<button class="btn-export-csv" data-sec="{key}">&#8615; CSV</button>'
            f'</div>'
            f'<div class="tabla-wrap">'
            f'<table class="mo-table" id="tabla-{key}">'
            f'<thead><tr>'
            f'<th>Ticket</th><th>Subcategoría</th>'
            f'<th>Horas sin gestión</th><th>Última gestión</th><th>Estado</th>'
            f'</tr></thead>'
            f'<tbody>\n{rows_html}</tbody>'
            f'</table></div>'
            f'</section>\n'
        )

    # KPI GLOBAL — agrega todas las secciones
    total_global_computables = 0
    total_global_incumple    = 0
    for sec in DISPLAY_SECCIONES:
        rows = results[sec["key"]]
        if sec["key"] == "logistica":
            computables = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"]
        else:
            computables = rows
        total_global_computables += len(computables)
        total_global_incumple    += len([r for r in computables if r.get("estado_sla") == "INCUMPLE"])

    pct_global = round(
        100 * (total_global_computables - total_global_incumple) / total_global_computables, 1
    ) if total_global_computables > 0 else 100.0
    color_global = kpi_color(pct_global)

    kpi_global_html = (
        f'<div class="kpi-global" style="border-left:6px solid {color_global}">'
        f'<div class="kpi-global-label">Resumen global &middot; todas las colas</div>'
        f'<div style="display:flex;align-items:baseline;gap:1.5rem;flex-wrap:wrap">'
        f'<div>'
        f'<span class="kpi-global-num" style="color:{color_global}">{total_global_incumple}</span>'
        f'<span class="kpi-global-sub"> tickets INCUMPLE de {total_global_computables} computables</span>'
        f'</div>'
        f'<div class="kpi-global-pct" style="color:{color_global}">{pct_global}% cumplimiento global</div>'
        f'</div>'
        f'<div style="margin-top:0.6rem;font-size:0.78rem;color:var(--text-muted)">'
        f'Tickets bajo responsabilidad activa de SAT2 (excluidos: contrata con cita activa, '
        f'proveedor externo en gesti&oacute;n). '
        f'Medici&oacute;n: INCUMPLE si supera el SLA de cada cola sin gesti&oacute;n registrada.'
        f'</div>'
        f'</div>'
    )

    return HTML_TEMPLATE.format(
        fecha_informe=fecha_str,
        hora_generacion=hora_str,
        kpi_global=kpi_global_html,
        kpi_cards=kpi_html,
        sections=sections_html,
    )


# ─────────────────────────────────────────────────────────────────
# PLANTILLA HTML (fondo blanco, estilo MasOrange)
# ─────────────────────────────────────────────────────────────────
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Informe SLA Fijo &mdash; {fecha_informe} &mdash; MasOrange</title>
  <style>
    /* ── TOKENS MARCA ───────────────────────────────────────────── */
    :root {{
      --mo-orange:      #FF5900;
      --mo-black:       #000000;
      --mo-white:       #FFFFFF;
      --mo-gray-light:  #F2F2F2;
      --mo-gray-mid:    #999999;
      --mo-shadow-sm:   0 2px 8px rgba(0,0,0,.10);
      --mo-shadow-md:   0 4px 16px rgba(0,0,0,.14);
      --mo-margin:      clamp(1.5rem, 4vw, 4rem);

      /* Semánticos — modo claro */
      --bg-page:         #FFFFFF;
      --bg-card:         #FFFFFF;
      --bg-strip:        #F2F2F2;
      --text-main:       #000000;
      --text-muted:      #999999;
      --border-main:     #000000;
      --border-subtle:   #E0E0E0;
      --nav-bg:          #FFFFFF;
      --mo-circle-color: #000000;   /* O del logo: negro en claro */
    }}

    /* ── DARK MODE automático (preferencia del sistema) ────────── */
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg-page:         #0d0d0d;
        --bg-card:         #1a1a1a;
        --bg-strip:        #111111;
        --text-main:       #FFFFFF;
        --text-muted:      #888888;
        --border-main:     #FFFFFF;
        --border-subtle:   #2a2a2a;
        --nav-bg:          #0d0d0d;
        --mo-circle-color: #FFFFFF; /* O del logo: blanco en oscuro */
      }}
    }}

    /* ── DARK MODE manual (botón toggle) ───────────────────────── */
    [data-theme="dark"] {{
      --bg-page:         #0d0d0d;
      --bg-card:         #1a1a1a;
      --bg-strip:        #111111;
      --text-main:       #FFFFFF;
      --text-muted:      #888888;
      --border-main:     #FFFFFF;
      --border-subtle:   #2a2a2a;
      --nav-bg:          #0d0d0d;
      --mo-circle-color: #FFFFFF;
    }}
    [data-theme="light"] {{
      --bg-page:         #FFFFFF;
      --bg-card:         #FFFFFF;
      --bg-strip:        #F2F2F2;
      --text-main:       #000000;
      --text-muted:      #999999;
      --border-main:     #000000;
      --border-subtle:   #E0E0E0;
      --nav-bg:          #FFFFFF;
      --mo-circle-color: #000000;
    }}

    /* ── RESET ──────────────────────────────────────────────────── */
    * {{ font-family: Arial, Helvetica, sans-serif; box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg-page); color: var(--text-main); font-size: 1rem; line-height: 1.5; transition: background .2s, color .2s; }}
    a {{ color: var(--mo-orange); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* ── NAV ────────────────────────────────────────────────────── */
    .mo-nav {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 var(--mo-margin);
      height: 56px;
      background: var(--nav-bg); border-bottom: 1px solid var(--border-subtle);
      position: sticky; top: 0; z-index: 100;
    }}
    .mo-nav-left {{ display: flex; align-items: center; gap: 1.5rem; height: 100%; }}
    .mo-nav-brand {{
      font-size: 0.72rem; font-weight: 700; letter-spacing: .06em;
      text-transform: uppercase; color: var(--text-muted); white-space: nowrap;
    }}
    .mo-nav-links {{
      display: flex; gap: 0; list-style: none; height: 100%; margin: 0; padding: 0;
    }}
    .mo-nav-links a {{
      display: flex; align-items: center; height: 100%;
      padding: 0 1.1rem; font-size: 0.875rem; color: var(--text-muted);
      border-bottom: 3px solid transparent;
      transition: color .15s, border-color .15s;
    }}
    .mo-nav-links a:hover {{ color: var(--text-main); text-decoration: none; }}
    .mo-nav-links a.active {{
      color: var(--text-main); font-weight: 700;
      border-bottom-color: var(--mo-orange);
    }}
    .mo-nav-links a.disabled {{
      color: var(--border-subtle); cursor: default; pointer-events: none;
    }}
    .mo-logo {{ width: 64px; height: auto; }}

    /* Toggle dark/light */
    .mo-theme-btn {{
      background: none; border: 1.5px solid var(--border-subtle);
      border-radius: 20px; padding: 0.3rem 0.8rem;
      cursor: pointer; font-size: 0.8rem; color: var(--text-main);
      display: flex; align-items: center; gap: 0.4rem;
      transition: border-color .2s, color .2s;
    }}
    .mo-theme-btn:hover {{ border-color: var(--mo-orange); color: var(--mo-orange); }}
    .mo-theme-icon {{ font-size: 1rem; }}

    /* ── HERO ───────────────────────────────────────────────────── */
    .mo-hero {{
      background: #000000; color: #FFFFFF;
      padding: 2.5rem var(--mo-margin) 2rem;
    }}
    .mo-hero h1 {{
      font-size: clamp(1.8rem, 4vw, 2.5rem); font-weight: 700;
      color: #FFFFFF; margin-bottom: 0.5rem;
    }}
    .mo-hero .subtitulo {{ font-size: 1rem; color: #cccccc; margin-bottom: 1rem; }}

    /* ── BADGES ─────────────────────────────────────────────────── */
    .mo-badge {{
      display: inline-block; font-size: 0.72rem; font-weight: 700;
      padding: 0.25rem 0.6rem; border-radius: 2px;
      text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .mo-badge-gray {{ background: var(--bg-strip); color: var(--text-main); margin-left: 0.4rem; }}

    /* ── KPI GLOBAL ─────────────────────────────────────────────── */
    .kpi-global-wrap {{
      background: var(--bg-strip);
      padding: 1.5rem var(--mo-margin) 0;
    }}
    .kpi-global {{
      background: var(--bg-card); border-radius: 4px;
      padding: 1.25rem 1.75rem; box-shadow: var(--mo-shadow-sm);
    }}
    .kpi-global-label {{
      font-size: 0.72rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--text-muted); margin-bottom: 0.6rem;
    }}
    .kpi-global-num  {{ font-size: 2.4rem; font-weight: 700; line-height: 1; }}
    .kpi-global-sub  {{ font-size: 0.9rem; color: var(--text-muted); }}
    .kpi-global-pct  {{ font-size: 1.1rem; font-weight: 700; }}

    /* ── KPI GRID ───────────────────────────────────────────────── */
    .kpi-grid {{
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 1.25rem; padding: 1rem var(--mo-margin) 2rem;
      background: var(--bg-strip);
    }}
    .kpi-card {{
      background: var(--bg-card); border-radius: 4px;
      padding: 1.25rem 1.5rem; box-shadow: var(--mo-shadow-sm);
    }}
    .kpi-label {{
      font-size: 0.72rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--text-muted); margin-bottom: 0.6rem;
    }}
    .kpi-incumple {{ font-size: 2.8rem; font-weight: 700; line-height: 1; margin-bottom: 0.2rem; }}
    .kpi-sub     {{ font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.6rem; }}
    .kpi-pct     {{ font-size: 0.95rem; font-weight: 700; }}

    /* ── SECCIONES ──────────────────────────────────────────────── */
    .tabla-seccion {{ padding: 2.5rem var(--mo-margin) 0; }}
    .seccion-header {{
      display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
      margin-bottom: 1rem; padding-bottom: 0.75rem;
      border-bottom: 2px solid var(--border-main);
    }}
    .seccion-header h2 {{ font-size: 1.4rem; font-weight: 700; }}
    .tabla-wrap {{ overflow-x: auto; margin-bottom: 0.5rem; }}

    /* ── TABLA ──────────────────────────────────────────────────── */
    .mo-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    .mo-table th {{
      background: #000000; color: #FFFFFF;
      font-weight: 700; text-align: left; padding: 0.7rem 1rem;
    }}
    .mo-table td {{ padding: 0.7rem 1rem; border-bottom: 1px solid var(--border-subtle); color: var(--text-main); }}
    .mo-table tr:nth-child(even) td {{ background: var(--bg-strip); }}
    .mo-table tr:hover td {{ background: rgba(255,89,0,.08); }}
    .toggle-cell {{
      text-align: center; cursor: pointer; color: var(--mo-orange);
      font-size: 0.82rem; padding: 0.5rem !important;
      background: var(--bg-card) !important;
    }}
    .toggle-row:hover .toggle-cell {{ background: var(--bg-strip) !important; }}
    /* Filas críticas >96h */
    .row-critico td {{ background: rgba(198,40,40,.07) !important; }}
    .row-critico:hover td {{ background: rgba(198,40,40,.14) !important; }}
    [data-theme="dark"] .row-critico td {{ background: rgba(198,40,40,.15) !important; }}
    /* Barra de filtros tabla */
    .tabla-toolbar {{
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      padding: 8px 0 10px;
    }}
    .tabla-toolbar input {{
      font-family: Arial,Helvetica,sans-serif; font-size: 0.8rem;
      padding: 4px 10px; border: 1.5px solid var(--border-subtle);
      border-radius: 4px; background: var(--bg-card); color: var(--text-main);
      width: 200px;
    }}
    .tabla-toolbar input:focus {{ outline: none; border-color: var(--mo-orange); }}
    .tabla-filter-btn {{
      font-family: Arial,Helvetica,sans-serif; font-size: 0.75rem; font-weight: 700;
      padding: 4px 12px; border-radius: 4px; cursor: pointer;
      border: 1.5px solid var(--border-subtle);
      background: var(--bg-card); color: var(--text-muted);
      transition: border-color .15s, color .15s, background .15s;
    }}
    .tabla-filter-btn:hover {{ border-color: var(--mo-orange); color: var(--mo-orange); }}
    .tabla-filter-btn.active {{ background: var(--mo-orange); border-color: var(--mo-orange); color: #fff; }}
    .btn-export-csv {{
      font-family: Arial,Helvetica,sans-serif; font-size: 0.75rem; font-weight: 700;
      padding: 4px 14px; border-radius: 4px; cursor: pointer;
      border: 1.5px solid #2E7D32; background: var(--bg-card); color: #2E7D32;
      margin-left: auto; transition: background .15s, color .15s;
    }}
    .btn-export-csv:hover {{ background: #2E7D32; color: #fff; }}
    .tabla-count {{ font-size: 0.75rem; color: var(--text-muted); }}
    /* Auto-refresh badge */
    #refresh-badge {{
      position: fixed; bottom: 16px; right: 16px; z-index: 200;
      background: #000; color: #aaa; font-size: 0.72rem;
      padding: 4px 10px; border-radius: 20px; border: 1px solid #333;
      cursor: pointer;
    }}
    #refresh-badge:hover {{ color: #fff; }}

    /* ── FOOTER ─────────────────────────────────────────────────── */
    .mo-footer {{
      background: #000000; color: #FFFFFF;
      padding: 1.75rem var(--mo-margin); margin-top: 3rem;
      display: flex; align-items: center; justify-content: space-between; gap: 1rem;
      flex-wrap: wrap;
    }}
    .mo-footer p {{ color: #cccccc; font-size: 0.8rem; margin: 0; }}

    /* ── RESPONSIVE ─────────────────────────────────────────────── */
    @media (max-width: 900px) {{ .kpi-grid {{ grid-template-columns: repeat(2,1fr); }} }}
    @media (max-width: 540px) {{ .kpi-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>

  <!-- NAV -->
  <nav class="mo-nav">
    <div class="mo-nav-left">
      <span class="mo-nav-brand">BOST &middot; SLA Dashboard</span>
      <ul class="mo-nav-links">
        <li><a href="global.html">Global</a></li>
        <li><a href="#" class="active">Fijo</a></li>
        <li><a href="tv.html" class="disabled" title="Próximamente">TV</a></li>
      </ul>
      <button class="mo-theme-btn" id="themeToggle" title="Cambiar tema">
        <span class="mo-theme-icon" id="themeIcon">&#9790;</span>
        <span id="themeLabel">Modo oscuro</span>
      </button>
    </div>
    <svg class="mo-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" role="img" aria-label="MasOrange">
      <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
      <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="var(--mo-circle-color)" stroke-width="10"/>
    </svg>
  </nav>

  <!-- HERO (siempre negro — zona de impacto) -->
  <header class="mo-hero">
    <h1>Informe SLA Fijo</h1>
    <p class="subtitulo">Tickets sin gesti&oacute;n bajo responsabilidad SAT2 &middot; {fecha_informe}</p>
    <span class="mo-badge" style="background:#FF5900;color:#fff">Datos cargados a las 08:30h</span>
  </header>

  <!-- KPI GLOBAL -->
  <div class="kpi-global-wrap">
    {kpi_global}
  </div>

  <!-- KPI CARDS -->
  <div class="kpi-grid">
    {kpi_cards}
  </div>

  <!-- TABLAS -->
  <main>
    {sections}
    <div style="height:1rem"></div>
  </main>

  <!-- FOOTER (siempre negro) -->
  <footer class="mo-footer">
    <!-- Logo footer: + naranja, O blanco (fondo negro siempre) -->
    <svg class="mo-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" role="img" aria-label="MasOrange">
      <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
      <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
      <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="#FFFFFF" stroke-width="10"/>
    </svg>
    <p>Generado autom&aacute;ticamente &middot; BOST MasOrange &middot; {fecha_informe} a las {hora_generacion}h</p>
  </footer>

  <div id="refresh-badge" title="Refresco automático cada 5 min. Haz clic para refrescar ahora.">&#8635; auto</div>

  <script>
    /* ── Toggle de filas CUMPLE ─────────────────────────────────── */
    document.querySelectorAll('.toggle-row').forEach(function(row) {{
      row.addEventListener('click', function() {{
        var sec = row.dataset.sec;
        var hidden = document.querySelectorAll('.otros-row-' + sec);
        var cell = row.querySelector('.toggle-cell');
        var isOpen = hidden[0] && hidden[0].style.display !== 'none';
        hidden.forEach(function(r) {{ r.style.display = isOpen ? 'none' : ''; }});
        if (isOpen) {{
          cell.textContent = cell.textContent.replace('▲ Ocultar', '▼ Ver').replace('Ocultar', 'Ver');
          cell.textContent = cell.textContent.replace('▲', '▼');
        }} else {{
          cell.textContent = cell.textContent.replace('▼ Ver', '▲ Ocultar').replace('Ver', 'Ocultar');
          cell.textContent = cell.textContent.replace('▼', '▲');
        }}
      }});
    }});

    /* ── Filtros de tabla ───────────────────────────────────────── */
    function updateCount(sec) {{
      var tabla = document.getElementById('tabla-' + sec);
      if (!tabla) return;
      var visible = tabla.querySelectorAll('tbody tr:not(.toggle-row):not([style*="display:none"])');
      var incumple = 0;
      visible.forEach(function(r) {{ if (r.classList.contains('row-critico') || (r.dataset.horas && parseFloat(r.dataset.horas) >= 24)) incumple++; }});
      var badge = document.getElementById('count-' + sec);
      if (badge) badge.textContent = visible.length + ' visibles';
    }}

    function applyFilters(sec) {{
      var input = document.querySelector('.tabla-filter-input[data-sec="' + sec + '"]');
      var activeBtn = document.querySelector('.tabla-filter-btn.active[data-sec="' + sec + '"]');
      var text = input ? input.value.toLowerCase() : '';
      var mode = activeBtn ? activeBtn.dataset.filter : 'all';
      var tabla = document.getElementById('tabla-' + sec);
      if (!tabla) return;
      tabla.querySelectorAll('tbody tr').forEach(function(row) {{
        if (row.classList.contains('toggle-row')) return;
        var categ = (row.dataset.categ || '').toLowerCase();
        var horas = parseFloat(row.dataset.horas) || 0;
        var matchText = !text || categ.indexOf(text) !== -1;
        var matchMode = mode === 'all' || (mode === 'critico' && horas > 96);
        row.style.display = (matchText && matchMode) ? '' : 'none';
      }});
      updateCount(sec);
    }}

    document.querySelectorAll('.tabla-filter-input').forEach(function(input) {{
      input.addEventListener('input', function() {{ applyFilters(this.dataset.sec); }});
    }});

    document.querySelectorAll('.tabla-filter-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var sec = this.dataset.sec;
        document.querySelectorAll('.tabla-filter-btn[data-sec="' + sec + '"]').forEach(function(b) {{ b.classList.remove('active'); }});
        this.classList.add('active');
        applyFilters(sec);
      }});
    }});

    /* ── Exportar CSV ───────────────────────────────────────────── */
    document.querySelectorAll('.btn-export-csv').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var sec = this.dataset.sec;
        var tabla = document.getElementById('tabla-' + sec);
        if (!tabla) return;
        var rows = [['Ticket','Subcategoría','Horas sin gestión','Última gestión','Estado']];
        tabla.querySelectorAll('tbody tr').forEach(function(row) {{
          if (row.classList.contains('toggle-row')) return;
          if (row.style.display === 'none') return;
          var cells = row.querySelectorAll('td');
          if (cells.length < 5) return;
          rows.push([
            cells[0].textContent.trim(),
            cells[1].textContent.trim(),
            cells[2].textContent.trim(),
            cells[3].textContent.trim(),
            cells[4].textContent.trim()
          ]);
        }});
        var csv = rows.map(function(r) {{
          return r.map(function(c) {{ return '"' + c.replace(/"/g, '""') + '"'; }}).join(',');
        }}).join('\n');
        var blob = new Blob(['﻿' + csv], {{type: 'text/csv;charset=utf-8;'}});
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'sla_' + sec + '_{fecha_informe}.csv';
        a.click();
      }});
    }});

    /* ── Auto-refresco ──────────────────────────────────────────── */
    var refreshSeconds = 300;
    var countdown = refreshSeconds;
    var badge = document.getElementById('refresh-badge');
    var timer = setInterval(function() {{
      countdown--;
      if (badge) badge.textContent = '↻ ' + countdown + 's';
      if (countdown <= 0) {{ location.reload(); }}
    }}, 1000);
    if (badge) badge.addEventListener('click', function() {{ location.reload(); }});

    /* ── Dark / Light mode toggle ───────────────────────────────── */
    (function() {{
      var btn   = document.getElementById('themeToggle');
      var icon  = document.getElementById('themeIcon');
      var label = document.getElementById('themeLabel');
      var html  = document.documentElement;

      var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      var stored = localStorage.getItem('mo-theme');
      var isDark = stored ? stored === 'dark' : prefersDark;

      function applyTheme(dark) {{
        html.setAttribute('data-theme', dark ? 'dark' : 'light');
        icon.textContent  = dark ? '☀' : '☽';
        label.textContent = dark ? 'Modo claro' : 'Modo oscuro';
        localStorage.setItem('mo-theme', dark ? 'dark' : 'light');
      }}

      applyTheme(isDark);

      btn.addEventListener('click', function() {{
        isDark = !isDark;
        applyTheme(isDark);
      }});
    }})();
  </script>

</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# EMAIL VIA OUTLOOK COM
# ─────────────────────────────────────────────────────────────────
def build_email_body(results, now):
    """
    Genera el cuerpo HTML del email para directores y proveedores:
    - Estado global inmediato (semáforo visual)
    - KPI por cola con barra de progreso
    - Análisis automático de 2-3 puntos clave
    - Pie con nota de informe adjunto
    Preparado para TV: añadir más entradas a SECCIONES es suficiente.
    """
    fecha_str = now.strftime("%d/%m/%Y")
    hora_str  = now.strftime("%H:%M")
    dia_semana = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][now.weekday()]

    # ── Calcular KPIs por cola ──────────────────────────────────────
    kpis = []
    total_computables = 0
    total_incumple    = 0

    for sec in DISPLAY_SECCIONES:
        rows = results[sec["key"]]
        if sec["key"] == "logistica":
            computables = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"]
        else:
            computables = rows
        n_comp     = len(computables)
        n_incumple = len([r for r in computables if r.get("estado_sla") == "INCUMPLE"])
        pct        = round(100 * (n_comp - n_incumple) / n_comp, 1) if n_comp > 0 else 100.0
        color      = kpi_color(pct)
        total_computables += n_comp
        total_incumple    += n_incumple
        kpis.append({
            "label": sec["label"], "sla": sec["sla"],
            "n_comp": n_comp, "n_incumple": n_incumple,
            "pct": pct, "color": color,
        })

    pct_global   = round(100 * (total_computables - total_incumple) / total_computables, 1) if total_computables > 0 else 100.0
    color_global = kpi_color(pct_global)

    # ── Semáforo de estado global ───────────────────────────────────
    if pct_global >= 80:
        estado_label = "ESTADO: CORRECTO"
        estado_bg    = "#1B5E20"
        estado_emoji = "✅"
    elif pct_global >= 50:
        estado_label = "ESTADO: ATENCIÓN"
        estado_bg    = "#E65100"
        estado_emoji = "⚠️"
    else:
        estado_label = "ESTADO: CRÍTICO"
        estado_bg    = "#B71C1C"
        estado_emoji = "🔴"

    # ── Barras de progreso por cola ─────────────────────────────────
    cards_html = ""
    for k in kpis:
        bar_pct   = max(2, k["pct"])   # mínimo visual de 2% para que se vea la barra
        cards_html += f"""
        <tr>
          <td style="padding:10px 0 10px 0;border-bottom:1px solid #f0f0f0">
            <table style="width:100%;border-collapse:collapse">
              <tr>
                <td style="width:110px;font-weight:700;font-size:0.875rem;color:#000;vertical-align:middle">{k['label']}</td>
                <td style="vertical-align:middle;padding:0 12px">
                  <!-- Barra de progreso -->
                  <div style="background:#f0f0f0;border-radius:3px;height:10px;overflow:hidden">
                    <div style="background:{k['color']};width:{bar_pct}%;height:10px;border-radius:3px"></div>
                  </div>
                </td>
                <td style="width:52px;text-align:right;font-weight:700;font-size:1rem;color:{k['color']};vertical-align:middle">{k['pct']}%</td>
                <td style="width:80px;text-align:right;font-size:0.78rem;color:#999;vertical-align:middle;padding-left:8px">{k['n_incumple']} / {k['n_comp']}<br><span style="font-size:0.7rem">SLA {k['sla']}</span></td>
              </tr>
            </table>
          </td>
        </tr>"""

    # ── Análisis automático ─────────────────────────────────────────
    puntos = []

    # Peor cola — solo si tiene volumen suficiente (>=5 tickets) e incumplimientos reales
    colas_significativas = [k for k in kpis if k["n_comp"] >= 5 and k["n_incumple"] > 0]
    if colas_significativas:
        peor = min(colas_significativas, key=lambda x: x["pct"])
        puntos.append(
            f"La cola con mayor incumplimiento es <strong>{peor['label']}</strong> "
            f"({peor['n_incumple']} de {peor['n_comp']} tickets, {peor['pct']}% cumplimiento)."
        )
    else:
        total_inc = sum(k["n_incumple"] for k in kpis)
        if total_inc == 0:
            puntos.append("Todas las colas están en cumplimiento hoy. Sin incumplimientos registrados.")
        else:
            puntos.append("El volumen de tickets en todas las colas es bajo hoy — los datos pueden no ser representativos.")

    # Tickets críticos >96h en STFIJO
    stfijo_rows = results.get("stfijo", [])
    criticos = [r for r in stfijo_rows if r.get("estado_sla") == "INCUMPLE"
                and (r.get("horas_sin_gestion") or 0) > 96]
    if criticos:
        claves_criticos = ", ".join(
            f'<a href="https://tgjira.masmovil.com/browse/{r.get("CLAVE","")}" style="color:#FF5900">{r.get("CLAVE","")}</a>'
            for r in criticos
        )
        puntos.append(
            f"<strong>{len(criticos)} tickets en STFIJO-ZL superan las 96h sin gestión</strong>: {claves_criticos}."
        )
    else:
        puntos.append("No hay tickets con más de 96h sin gestión en STFIJO-ZL.")

    # Cola con mejor cumplimiento
    mejor = max(kpis, key=lambda x: x["pct"])
    if mejor["pct"] >= 80:
        puntos.append(
            f"{mejor['label']} mantiene un cumplimiento correcto ({mejor['pct']}%)."
        )
    else:
        puntos.append(
            f"Ninguna cola supera el 80% de cumplimiento hoy. Se recomienda revisión del equipo."
        )

    analisis_html = "".join(
        f'<li style="margin-bottom:8px;color:#333;font-size:0.875rem;line-height:1.5">{p}</li>'
        for p in puntos
    )

    # ── Resumen IA (P6 — BST-13132) ────────────────────────────────
    resumen_ia_texto = generar_resumen_ia(kpis, pct_global, results, now)
    if resumen_ia_texto:
        resumen_ia_html = f"""
  <!-- RESUMEN IA (P6) -->
  <div style="padding:16px 28px 16px;background:#fff;border-top:1px solid #f0f0f0">
    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#FF5900;margin-bottom:8px">Análisis IA</div>
    <p style="margin:0;font-size:0.875rem;color:#333;line-height:1.6">{resumen_ia_texto}</p>
  </div>"""
    else:
        resumen_ia_html = ""

    # ── Nota evolución (placeholder hasta BST-13142) ───────────────
    evolucion_html = (
        '<div style="background:#fffbe6;border-left:3px solid #FFD600;padding:10px 14px;'
        'margin-top:0;font-size:0.78rem;color:#666;border-radius:0 3px 3px 0">'
        '📈 <strong>Evolución histórica</strong>: disponible próximamente — '
        'en desarrollo el registro diario de KPIs para mostrar tendencia semanal/mensual.'
        '</div>'
    )

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Arial,Helvetica,sans-serif;background:#f2f2f2;margin:0;padding:20px 0">
<div style="max-width:580px;margin:0 auto;background:#fff;border-radius:4px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.12)">

  <!-- CABECERA negra -->
  <div style="background:#000;padding:22px 28px 18px;display:table;width:100%;box-sizing:border-box">
    <div style="display:table-cell;vertical-align:middle">
      <div style="font-size:1.25rem;font-weight:700;color:#fff;margin-bottom:2px">Informe SLA Fijo</div>
      <div style="font-size:0.8rem;color:#aaa">{dia_semana}, {fecha_str} &middot; Datos a las 08:30h</div>
    </div>
    <!-- Logo +O -->
    <div style="display:table-cell;vertical-align:middle;text-align:right;width:64px">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" width="56" height="auto" aria-label="MasOrange">
        <rect x="4"  y="24" width="16" height="16" fill="#FF5900"/>
        <rect x="20" y="8"  width="16" height="16" fill="#FF5900"/>
        <rect x="20" y="24" width="16" height="16" fill="#FF5900"/>
        <rect x="20" y="40" width="16" height="16" fill="#FF5900"/>
        <rect x="36" y="24" width="16" height="16" fill="#FF5900"/>
        <circle cx="104" cy="34" r="28" fill="none" stroke="#fff" stroke-width="10"/>
      </svg>
    </div>
  </div>

  <!-- SEMÁFORO DE ESTADO -->
  <div style="background:{estado_bg};padding:14px 28px;text-align:center">
    <span style="font-size:1rem;font-weight:700;color:#fff;letter-spacing:.04em">{estado_emoji} {estado_label}</span>
  </div>

  <!-- KPI GLOBAL -->
  <div style="padding:20px 28px 16px;border-bottom:1px solid #f0f0f0;background:#fff">
    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#999;margin-bottom:8px">Cumplimiento global &mdash; todas las colas</div>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="vertical-align:middle">
          <span style="font-size:3rem;font-weight:700;color:{color_global};line-height:1">{pct_global}%</span>
          <div style="font-size:0.82rem;color:#666;margin-top:4px">{total_incumple} INCUMPLE &nbsp;·&nbsp; {total_computables} computables</div>
        </td>
        <td style="vertical-align:middle;text-align:right;padding-left:16px">
          <!-- Mini barra global -->
          <div style="background:#f0f0f0;border-radius:4px;height:14px;width:160px;overflow:hidden;margin-left:auto">
            <div style="background:{color_global};width:{max(2, pct_global)}%;height:14px;border-radius:4px"></div>
          </div>
          <div style="font-size:0.7rem;color:#999;margin-top:4px;text-align:right">{total_computables - total_incumple} dentro de SLA</div>
        </td>
      </tr>
    </table>
  </div>

  <!-- COLAS: barras de progreso -->
  <div style="padding:16px 28px 4px;background:#fff">
    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#999;margin-bottom:4px">Detalle por cola</div>
    <table style="width:100%;border-collapse:collapse">
      {cards_html}
    </table>
  </div>

  <!-- ANÁLISIS AUTOMÁTICO -->
  <div style="padding:16px 28px 16px;background:#fafafa;border-top:1px solid #f0f0f0;border-bottom:1px solid #f0f0f0">
    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#999;margin-bottom:10px">Análisis del día</div>
    <ul style="margin:0;padding-left:18px">
      {analisis_html}
    </ul>
  </div>

  {resumen_ia_html}

  <!-- EVOLUCIÓN (placeholder) -->
  <div style="padding:12px 28px 16px;background:#fff">
    {evolucion_html}
  </div>

  <!-- PIE -->
  <div style="background:#000;padding:12px 28px;font-size:0.72rem;color:#888;display:table;width:100%;box-sizing:border-box">
    <span style="display:table-cell;vertical-align:middle">Informe completo adjunto &middot; BOST MasOrange</span>
    <span style="display:table-cell;vertical-align:middle;text-align:right;color:#555">{fecha_str} {hora_str}h</span>
  </div>

</div>
</body>
</html>"""


def build_email_prediccion(rows_riesgo, now):
    """
    Genera el cuerpo HTML del email de alerta de predicción SLA (BST-13236).
    Solo se envía si hay tickets EN_RIESGO (18h-24h laborables sin gestión).
    Los tickets ya en INCUMPLE van al informe normal, no aquí.
    """
    fecha_str   = now.strftime("%d/%m/%Y")
    hora_str    = now.strftime("%H:%M")
    n_criticos  = len([r for r in rows_riesgo if r.get("nivel_urgencia","").startswith("🔴")])
    n_urgentes  = len([r for r in rows_riesgo if r.get("nivel_urgencia","").startswith("🟠")])
    n_atencion  = len([r for r in rows_riesgo if r.get("nivel_urgencia","").startswith("🟡")])

    # Construir filas de la tabla
    filas_html = ""
    for r in rows_riesgo:
        clave   = r.get("clave") or r.get("CLAVE","")
        horas   = r.get("horas_sin_gestion") or r.get("HORAS_SIN_GESTION",0)
        restant = r.get("horas_restantes_sla") or r.get("HORAS_RESTANTES_SLA",0)
        estado  = r.get("estado_averia") or r.get("ESTADO_AVERIA","")
        origen  = r.get("origen_reloj") or r.get("ORIGEN_RELOJ","")
        urgencia = r.get("nivel_urgencia") or r.get("NIVEL_URGENCIA","🟡 ATENCIÓN")
        externo = r.get("nombre_externo") or r.get("NOMBRE_EXTERNO","") or "—"
        url = f"https://tgjira.masmovil.com/browse/{clave}"

        bg = "#fff5f5" if "CRÍTICO" in urgencia else ("#fff8f0" if "URGENTE" in urgencia else "#fffff8")
        filas_html += f"""
        <tr style="background:{bg};border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 12px;font-size:0.82rem;font-weight:600">
            <a href="{url}" style="color:#FF5900;text-decoration:none">{clave}</a>
          </td>
          <td style="padding:8px 12px;font-size:0.82rem;color:#333">{estado}</td>
          <td style="padding:8px 12px;font-size:0.82rem;color:#333;text-align:center"><strong>{horas}h</strong></td>
          <td style="padding:8px 12px;font-size:0.82rem;text-align:center">
            <strong style="color:{'#c0392b' if 'CRÍTICO' in urgencia else ('#e67e22' if 'URGENTE' in urgencia else '#f39c12')}">{restant}h</strong>
          </td>
          <td style="padding:8px 12px;font-size:0.75rem;color:#666">{origen}</td>
          <td style="padding:8px 12px;font-size:0.75rem;color:#888">{externo}</td>
          <td style="padding:8px 12px;font-size:0.82rem">{urgencia}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>⚠️ Alerta SLA Fijo — {fecha_str}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:700px;margin:20px auto;background:#fff;border-radius:4px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.12)">

  <!-- CABECERA -->
  <div style="background:#000;padding:20px 28px;display:flex;align-items:center;justify-content:space-between">
    <div>
      <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#FF5900;margin-bottom:4px">Alerta Predictiva · SLA Fijo</div>
      <div style="font-size:1.25rem;font-weight:700;color:#fff">⚠️ {len(rows_riesgo)} tickets en riesgo de incumplir</div>
      <div style="font-size:0.78rem;color:#999;margin-top:4px">{fecha_str} · {hora_str}h · Datos BQ a las 00:00h</div>
    </div>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" width="72" style="color:#FF5900;flex-shrink:0">
      <rect x="4"  y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="8"  width="16" height="16" fill="currentColor"/>
      <rect x="20" y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="40" width="16" height="16" fill="currentColor"/>
      <rect x="36" y="24" width="16" height="16" fill="currentColor"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="currentColor" stroke-width="10"/>
    </svg>
  </div>

  <!-- RESUMEN RÁPIDO -->
  <div style="padding:16px 28px;background:#fff;border-bottom:3px solid #FF5900;display:flex;gap:16px">
    <div style="text-align:center;flex:1;padding:12px;background:#fff5f5;border-radius:4px">
      <div style="font-size:1.6rem;font-weight:700;color:#c0392b">{n_criticos}</div>
      <div style="font-size:0.7rem;color:#999;text-transform:uppercase;letter-spacing:.05em">🔴 Crítico (&lt;2h)</div>
    </div>
    <div style="text-align:center;flex:1;padding:12px;background:#fff8f0;border-radius:4px">
      <div style="font-size:1.6rem;font-weight:700;color:#e67e22">{n_urgentes}</div>
      <div style="font-size:0.7rem;color:#999;text-transform:uppercase;letter-spacing:.05em">🟠 Urgente (&lt;4h)</div>
    </div>
    <div style="text-align:center;flex:1;padding:12px;background:#fffff8;border-radius:4px">
      <div style="font-size:1.6rem;font-weight:700;color:#f39c12">{n_atencion}</div>
      <div style="font-size:0.7rem;color:#999;text-transform:uppercase;letter-spacing:.05em">🟡 Atención (&lt;6h)</div>
    </div>
  </div>

  <!-- AVISO DATOS -->
  <div style="padding:10px 28px;background:#fffbea;border-bottom:1px solid #ffe58f">
    <p style="margin:0;font-size:0.75rem;color:#856404">
      ⏱️ <strong>Nota:</strong> Los estados de BQ reflejan la situación a las 00:00h.
      Gestiones realizadas entre medianoche y ahora pueden no estar reflejadas — verifica antes de actuar.
      Las horas sin gestión están calculadas a tiempo real ({hora_str}h).
    </p>
  </div>

  <!-- TABLA DE TICKETS -->
  <div style="padding:16px 28px 8px">
    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#FF5900;margin-bottom:10px">
      Tickets STFIJO-ZL · SLA 24h laborables · Ventana de riesgo: 18h–24h
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
      <thead>
        <tr style="background:#f8f8f8;border-bottom:2px solid #e0e0e0">
          <th style="padding:8px 12px;text-align:left;font-size:0.7rem;color:#666;text-transform:uppercase">Ticket</th>
          <th style="padding:8px 12px;text-align:left;font-size:0.7rem;color:#666;text-transform:uppercase">Estado</th>
          <th style="padding:8px 12px;text-align:center;font-size:0.7rem;color:#666;text-transform:uppercase">H. sin gestión</th>
          <th style="padding:8px 12px;text-align:center;font-size:0.7rem;color:#666;text-transform:uppercase">H. restantes</th>
          <th style="padding:8px 12px;text-align:left;font-size:0.7rem;color:#666;text-transform:uppercase">Origen reloj</th>
          <th style="padding:8px 12px;text-align:left;font-size:0.7rem;color:#666;text-transform:uppercase">Externo</th>
          <th style="padding:8px 12px;text-align:left;font-size:0.7rem;color:#666;text-transform:uppercase">Urgencia</th>
        </tr>
      </thead>
      <tbody>{filas_html}
      </tbody>
    </table>
  </div>

  <!-- PIE -->
  <div style="padding:14px 28px;background:#f8f8f8;border-top:1px solid #eee;margin-top:8px">
    <p style="margin:0;font-size:0.72rem;color:#999">
      Generado automáticamente · BOST MasOrange · {fecha_str} {hora_str}h ·
      Solo STFIJO-ZL (SLA 24h) · Umbral de alerta: ≥18h laborables sin gestión
    </p>
  </div>

</div>
</body></html>"""


def enviar_email_prediccion(rows_riesgo, now, intentos=3):
    """
    Envía el email de alerta predictiva SLA (BST-13236) via Outlook COM.
    Solo se llama si hay tickets en ventana de riesgo.
    """
    import win32com.client as win32
    asunto = f"⚠️ Alerta SLA Fijo — {len(rows_riesgo)} tickets en riesgo · {now.strftime('%d/%m/%Y')} {now.strftime('%H:%M')}h"
    html_body = build_email_prediccion(rows_riesgo, now)

    for intento in range(1, intentos + 1):
        try:
            outlook = win32.Dispatch("Outlook.Application")
            mail    = outlook.CreateItem(0)
            mail.To      = "samuel.minguez@masorange.es"
            mail.Subject = asunto
            mail.HTMLBody = html_body
            mail.Send()
            print(f"[prediccion] Email alerta enviado a samuel.minguez@masorange.es ({len(rows_riesgo)} tickets)")
            return
        except Exception as e:
            if intento < intentos:
                import time; time.sleep(5)
            else:
                print(f"[prediccion] ERROR al enviar email alerta: {e}")


def enviar_email(asunto, html_path, results, now, intentos=3):
    """
    Envía el informe por email via Outlook COM.
    - Cuerpo: resumen corto con KPIs por cola
    - Adjunto: informe HTML completo
    Requiere: pip install pywin32 y Outlook abierto en Windows.
    """
    import time
    try:
        import win32com.client
    except ImportError:
        print("[email] ERROR: pywin32 no instalado. Ejecuta: pip install pywin32")
        return False

    cuerpo = build_email_body(results, now)

    for intento in range(1, intentos + 1):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = MAIL_TO
            mail.Subject = asunto
            mail.HTMLBody = cuerpo
            mail.Attachments.Add(str(html_path))
            mail.Send()
            print(f"[email] Enviado a {MAIL_TO}")
            return True
        except Exception as e:
            print(f"[email] ERROR intento {intento}/{intentos}: {e}")
            if intento < intentos:
                print(f"[email] Reintentando en 30s...")
                time.sleep(30)
    return False


# ─────────────────────────────────────────────────────────────────
# HISTÓRICO PUENTE (BST-13142 bridge)
# Lee informes HTML ya generados y extrae los KPIs para alimentar
# la gráfica evolutiva del Global Dashboard.
# Solución temporal hasta que exista la tabla BQ oficial.
# ─────────────────────────────────────────────────────────────────

import re as _re

# ─────────────────────────────────────────────────────────────────
# P6 — RESUMEN IA (BST-13132)
# Genera un párrafo ejecutivo via Claude API (gateway MasOrange).
# Si el API no está disponible, falla silenciosamente (sin bloquear).
# ─────────────────────────────────────────────────────────────────

def generar_resumen_ia(kpis, pct_global, results, now):
    """
    Llama a Claude via gateway MasOrange y devuelve un párrafo ejecutivo
    de análisis del informe del día. Máximo 3 frases, orientado a acción.
    Requiere: variable de entorno CLAUDE_API_KEY.
    Falla silenciosamente si no está disponible.
    """
    import os, urllib.request, json as _json

    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        return ""

    # Datos para el prompt
    lineas = [f"Cumplimiento global: {pct_global}%"]
    for k in kpis:
        lineas.append(f"  {k['label']}: {k['pct']}% ({k['n_incumple']} INCUMPLE de {k['n_comp']} computables, SLA {k['sla']})")

    criticos_96 = [r for r in results.get("stfijo", [])
                   if r.get("estado_sla") == "INCUMPLE" and (r.get("horas_sin_gestion") or 0) > 96]

    prompt = (
        "Eres el sistema de análisis del equipo BOST (BackOffice Servicio Técnico) de MasOrange.\n"
        "Analiza los datos del informe SLA Fijo de hoy y genera UN ÚNICO párrafo ejecutivo "
        "(máximo 3 frases) en español. Sé directo y orientado a acción. "
        "No uses emojis. No repitas los números exactos del informe, aporta lectura de situación.\n\n"
        f"Datos del {now.strftime('%d/%m/%Y')}:\n"
        + "\n".join(lineas)
        + f"\nTickets STFIJO con más de 96h sin gestión: {len(criticos_96)}\n\n"
        "Genera solo el párrafo, sin título ni introducción."
    )

    try:
        payload = _json.dumps({
            "model": "claude-sonnet-4-5",
            "max_tokens": 220,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://llm.tools.cloud.masorange.es/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[P6] Resumen IA no disponible: {e}")
        return ""


def extraer_kpis_de_html(html_path):
    """
    Extrae KPIs de un informe HTML generado por este mismo script.
    Devuelve un dict con las 4 colas o None si no puede parsear.

    Estructura esperada en el HTML:
      class="kpi-pct"  → porcentaje de cumplimiento (%)
      class="kpi-incumple" → número de tickets que incumplen
    En el orden exacto de SECCIONES: stfijo, sgi, gior, logistica.
    """
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    pcts      = _re.findall(r'class="kpi-pct"[^>]*>([\d.]+)%\s*cumplimiento', text)
    incumples = _re.findall(r'class="kpi-incumple"[^>]*>([\d]+)<', text)

    if len(pcts) < 2 or len(incumples) < 2:
        return None

    # Compatibilidad: HTMLs viejos tienen 4 colas, nuevos tienen 2
    if len(pcts) >= 4:
        # HTML antiguo con 4 colas — calcular "fijo" como media ponderada
        stfijo_pct = float(pcts[0]); stfijo_inc = int(incumples[0])
        sgi_pct    = float(pcts[1]); sgi_inc    = int(incumples[1])
        gior_pct   = float(pcts[2]); gior_inc   = int(incumples[2])
        log_pct    = float(pcts[3]); log_inc    = int(incumples[3])
        # Porcentaje fijo = promedio simple de los 3 (sin datos de computables en HTML viejo)
        fijo_pct = round((stfijo_pct + sgi_pct + gior_pct) / 3, 1)
        fijo_inc = stfijo_inc + sgi_inc + gior_inc
        return {
            "fijo":      {"pct": fijo_pct,  "incumple": fijo_inc},
            "logistica": {"pct": log_pct,   "incumple": log_inc},
        }
    else:
        # HTML nuevo con 2 colas
        keys = [s["key"] for s in DISPLAY_SECCIONES]
        return {
            keys[i]: {"pct": float(pcts[i]), "incumple": int(incumples[i])}
            for i in range(2)
        }


def cargar_historico(dias=14):
    """
    Escanea REPORTES_DIR buscando informes con nombre informe_YYYY-MM-DD.html
    para los últimos `dias` días. Devuelve lista ordenada de dicts:
      [{"fecha": date, "stfijo": {"pct":..., "incumple":...}, ...}, ...]
    Solo incluye días para los que hay fichero Y los datos son parseables.
    """
    from datetime import date, timedelta

    historico = []
    today = date.today()

    for delta in range(dias - 1, -1, -1):  # más antiguo → más reciente
        d = today - timedelta(days=delta)
        fname = REPORTES_DIR / f"informe_{d.strftime('%Y-%m-%d')}.html"
        if not fname.exists():
            continue
        kpis = extraer_kpis_de_html(fname)
        if kpis is None:
            continue
        entry = {"fecha": d}
        entry.update(kpis)
        historico.append(entry)

    return historico


def _build_svg_chart(historico, width=560, height=220):
    """
    Genera un SVG inline con la evolución de % cumplimiento por cola.
    - Eje X: días (hasta 14 puntos)
    - Eje Y: 0-100%
    - Línea punteada en 80% (SLA target)
    - 4 líneas de color por cola
    Devuelve string SVG.
    """
    if not historico:
        return (
            '<div style="text-align:center;padding:40px;color:#aaa;font-size:0.85rem">'
            'Sin datos históricos disponibles aún. El gráfico aparecerá a partir del segundo día de ejecución.'
            '</div>'
        )

    PAD_L, PAD_R, PAD_T, PAD_B = 38, 16, 14, 32
    W = width - PAD_L - PAD_R
    H = height - PAD_T - PAD_B

    # Colores y etiquetas por cola
    COLA_COLORS = {
        "fijo":      "#FF5900",
        "logistica": "#9c27b0",
    }
    COLA_LABELS = {
        "fijo":      "STFIJO",
        "logistica": "Logística",
    }

    n = len(historico)
    xs = [PAD_L + (i / max(n - 1, 1)) * W for i in range(n)]

    def y_for(pct):
        return PAD_T + H - (pct / 100) * H

    lines_svg = ""

    # Línea target 80%
    y80 = y_for(80)
    lines_svg += (
        f'<line x1="{PAD_L}" y1="{y80:.1f}" x2="{PAD_L + W}" y2="{y80:.1f}" '
        f'stroke="#FFD600" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.9"/>'
        f'<text x="{PAD_L + W + 2}" y="{y80 + 4:.1f}" font-size="9" fill="#888">80%</text>'
    )

    # Líneas de colas
    for key in ["fijo", "logistica"]:
        color = COLA_COLORS[key]
        label = COLA_LABELS[key]
        puntos = [(xs[i], y_for(historico[i][key]["pct"])) for i in range(n) if key in historico[i]]
        if len(puntos) < 1:
            continue

        d = " ".join(
            f"{'M' if j == 0 else 'L'}{px:.1f},{py:.1f}"
            for j, (px, py) in enumerate(puntos)
        )
        lines_svg += f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'

        # Puntos
        for px, py in puntos:
            lines_svg += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{color}" stroke="#fff" stroke-width="1.2"/>'

        # Etiqueta al final
        if puntos:
            lx, ly = puntos[-1]
            lines_svg += (
                f'<text x="{lx + 5:.1f}" y="{ly + 4:.1f}" font-size="8.5" '
                f'fill="{color}" font-weight="bold">{label}</text>'
            )

    # Eje Y — ticks cada 20%
    grid_svg = ""
    for pct_tick in [0, 20, 40, 60, 80, 100]:
        yt = y_for(pct_tick)
        grid_svg += (
            f'<line x1="{PAD_L}" y1="{yt:.1f}" x2="{PAD_L + W}" y2="{yt:.1f}" '
            f'stroke="#e8e8e8" stroke-width="1"/>'
            f'<text x="{PAD_L - 4}" y="{yt + 3.5:.1f}" font-size="9" fill="#aaa" text-anchor="end">{pct_tick}%</text>'
        )

    # Eje X — etiquetas de fecha (máx 7 para no saturar)
    dates_svg = ""
    step = max(1, n // 7)
    for i in range(0, n, step):
        fecha_label = historico[i]["fecha"].strftime("%d/%m")
        dates_svg += (
            f'<text x="{xs[i]:.1f}" y="{PAD_T + H + 18}" '
            f'font-size="9" fill="#888" text-anchor="middle">{fecha_label}</text>'
        )
    # Siempre mostrar el último
    if n > 1:
        dates_svg += (
            f'<text x="{xs[-1]:.1f}" y="{PAD_T + H + 18}" '
            f'font-size="9" fill="#333" text-anchor="middle" font-weight="bold">'
            f'{historico[-1]["fecha"].strftime("%d/%m")}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'style="width:100%;font-family:Arial,Helvetica,sans-serif">'
        f'{grid_svg}{lines_svg}{dates_svg}'
        f'</svg>'
    )


def generar_global_html(results, now, historico):
    """
    Genera el Global Dashboard completo con datos reales:
    - KPI global calculado desde results (datos del día)
    - Gráfica SVG evolutiva con historico (puente de HTML pasados)
    - Análisis automático
    Escribe en REPORTES_DIR/global.html
    """
    fecha_str  = now.strftime("%d/%m/%Y")
    hora_str   = now.strftime("%H:%M")
    dia_semana = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][now.weekday()]

    # ── KPIs del día ─────────────────────────────────────────────────
    kpis_dia = []
    total_computables = 0
    total_incumple    = 0

    for sec in DISPLAY_SECCIONES:
        rows = results[sec["key"]]
        if sec["key"] == "logistica":
            computables = [r for r in rows if r.get("estado_sla") != "EXCLUIDO"]
        else:
            computables = rows
        n_comp     = len(computables)
        n_incumple = len([r for r in computables if r.get("estado_sla") == "INCUMPLE"])
        pct        = round(100 * (n_comp - n_incumple) / n_comp, 1) if n_comp > 0 else 100.0
        color      = kpi_color(pct)
        total_computables += n_comp
        total_incumple    += n_incumple
        kpis_dia.append({
            "label": sec["label"], "sla": sec["sla"],
            "n_comp": n_comp, "n_incumple": n_incumple,
            "pct": pct, "color": color,
        })

    sin_datos_hoy = (total_computables == 0)
    pct_global    = round(100 * (total_computables - total_incumple) / total_computables, 1) if total_computables > 0 else None
    color_global  = kpi_color(pct_global) if pct_global is not None else "#888"

    if sin_datos_hoy:
        estado_label = "SIN DATOS"
        estado_color = "#555"
        estado_bg    = "#f5f5f5"
        estado_emoji = "⏳"
    elif pct_global >= 80:
        estado_label = "CORRECTO"
        estado_color = "#1B5E20"
        estado_bg    = "#e8f5e9"
        estado_emoji = "✅"
    elif pct_global >= 50:
        estado_label = "ATENCIÓN"
        estado_color = "#E65100"
        estado_bg    = "#fff3e0"
        estado_emoji = "⚠️"
    else:
        estado_label = "CRÍTICO"
        estado_color = "#B71C1C"
        estado_bg    = "#ffebee"
        estado_emoji = "🔴"
    pct_global_display = f"{pct_global}%" if pct_global is not None else "—"

    # ── Cards de colas ────────────────────────────────────────────────
    cards_html = ""
    for k in kpis_dia:
        bar_pct = max(2, k["pct"])
        cards_html += f"""
        <div class="kpi-card">
          <div class="kpi-card-header">
            <span class="kpi-card-label">{k['label']}</span>
            <span class="kpi-card-sla">SLA {k['sla']}</span>
          </div>
          <div class="kpi-card-pct" style="color:{k['color']}">{k['pct']}%</div>
          <div class="kpi-bar-bg">
            <div class="kpi-bar-fill" style="background:{k['color']};width:{bar_pct}%"></div>
          </div>
          <div class="kpi-card-detail">{k['n_incumple']} incumplen · {k['n_comp']} computables</div>
        </div>"""

    # ── Análisis automático ───────────────────────────────────────────
    puntos = []
    mejor = max(kpis_dia, key=lambda x: x["pct"])
    colas_significativas_dia = [k for k in kpis_dia if k["n_comp"] >= 5 and k["n_incumple"] > 0]
    if colas_significativas_dia:
        peor = min(colas_significativas_dia, key=lambda x: x["pct"])
        puntos.append(
            f"La cola con mayor incumplimiento hoy es <strong>{peor['label']}</strong> "
            f"({peor['n_incumple']} de {peor['n_comp']} tickets, {peor['pct']}% cumplimiento)."
        )
    else:
        total_inc_dia = sum(k["n_incumple"] for k in kpis_dia)
        if total_inc_dia == 0:
            puntos.append("Todas las colas están en cumplimiento hoy. Sin incumplimientos registrados.")
        else:
            puntos.append("El volumen de tickets en todas las colas es bajo hoy — los datos pueden no ser representativos.")
    stfijo_rows = results.get("stfijo", [])
    criticos = [r for r in stfijo_rows if r.get("estado_sla") == "INCUMPLE" and (r.get("horas_sin_gestion") or 0) > 96]
    if criticos:
        claves_criticos = ", ".join(
            f'<a href="https://tgjira.masmovil.com/browse/{r.get("CLAVE","")}" style="color:#FF5900;text-decoration:none">{r.get("CLAVE","")}</a>'
            for r in criticos
        )
        puntos.append(
            f"<strong>{len(criticos)} tickets en STFIJO-ZL superan las 96h sin gestión</strong>: {claves_criticos}."
        )
    else:
        puntos.append("Sin tickets crónicos (&gt;96h) en STFIJO-ZL hoy.")
    if mejor["pct"] >= 80:
        puntos.append(f"{mejor['label']} lidera con {mejor['pct']}% de cumplimiento.")
    else:
        puntos.append("Ninguna cola supera el objetivo del 80% hoy — se recomienda revisión integral.")

    analisis_html = "".join(
        f'<li>{p}</li>'
        for p in puntos
    )

    # ── Nota de fuente del histórico ──────────────────────────────────
    if historico:
        dias_disp = len(historico)
        fuente_nota = (
            f'Datos reales de los últimos {dias_disp} día{"s" if dias_disp != 1 else ""} '
            f'(puente HTML · <a href="https://jiranext.masorange.es/browse/BST-13142" '
            f'style="color:#FF5900">BST-13142</a> para histórico oficial en BQ).'
        )
    else:
        fuente_nota = 'Sin datos históricos aún — el gráfico se alimentará a partir del segundo día de ejecución.'

    # ── JSON del histórico para chart interactivo ─────────────────────
    import json as _json_chart
    historico_js = _json_chart.dumps([
        {"fecha": e["fecha"].strftime("%Y-%m-%d"),
         **{k: {"pct": v["pct"], "incumple": v["incumple"]}
            for k, v in e.items() if k != "fecha"}}
        for e in historico
    ], ensure_ascii=False)

    chart_js = (
        "const CHART_DATA = " + historico_js + ";\n"
        "const COLA_COLORS = {fijo:'#FF5900',logistica:'#9c27b0'};\n"
        "const COLA_LABELS = {fijo:'STFIJO·SGI·GIOR',logistica:'Logística'};\n"
        "const COLA_KEYS   = ['fijo','logistica'];\n"
        "var activeDays = 7;\n"
        "var visibleColas = {fijo:true,logistica:true};\n"
        "var chartMode = 'colas';\n"
        "var slaChart = null;\n"
        "\n"
        "function isDarkMode(){\n"
        "  return document.documentElement.getAttribute('data-theme') === 'dark';\n"
        "}\n"
        "\n"
        "function buildChartConfig(data){\n"
        "  var dark = isDarkMode();\n"
        "  var gridColor = dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)';\n"
        "  var textColor = dark ? '#aaa' : '#666';\n"
        "  var labels = data.map(function(d){ return d.fecha.slice(5).replace('-','/'); });\n"
        "  var datasets = [];\n"
        "\n"
        "  // Línea objetivo 80%\n"
        "  datasets.push({\n"
        "    label: 'Objetivo 80%',\n"
        "    data: data.map(function(){ return 80; }),\n"
        "    borderColor: '#FFD600',\n"
        "    borderWidth: 1.5,\n"
        "    borderDash: [5,4],\n"
        "    pointRadius: 0,\n"
        "    fill: false,\n"
        "    tension: 0,\n"
        "    order: 99\n"
        "  });\n"
        "\n"
        "  if(chartMode === 'total'){\n"
        "    var pts = data.map(function(d){\n"
        "      var sum=0,cnt=0;\n"
        "      COLA_KEYS.forEach(function(k){ if(d[k]){ sum+=d[k].pct; cnt++; } });\n"
        "      return cnt>0 ? Math.round(sum/cnt*10)/10 : null;\n"
        "    });\n"
        "    datasets.push({\n"
        "      label: 'Total',\n"
        "      data: pts,\n"
        "      borderColor: dark ? '#fff' : '#333',\n"
        "      backgroundColor: dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',\n"
        "      borderWidth: 2.5,\n"
        "      pointRadius: 4,\n"
        "      pointHoverRadius: 6,\n"
        "      fill: true,\n"
        "      tension: 0.3\n"
        "    });\n"
        "  } else {\n"
        "    COLA_KEYS.forEach(function(key){\n"
        "      if(!visibleColas[key]) return;\n"
        "      var pts = data.map(function(d){ return d[key] ? d[key].pct : null; });\n"
        "      datasets.push({\n"
        "        label: COLA_LABELS[key],\n"
        "        data: pts,\n"
        "        borderColor: COLA_COLORS[key],\n"
        "        backgroundColor: COLA_COLORS[key] + '18',\n"
        "        borderWidth: 2,\n"
        "        pointRadius: 4,\n"
        "        pointHoverRadius: 7,\n"
        "        fill: false,\n"
        "        tension: 0.3,\n"
        "        _incumple: data.map(function(d){ return d[key] ? d[key].incumple : null; })\n"
        "      });\n"
        "    });\n"
        "  }\n"
        "\n"
        "  return {\n"
        "    type: 'line',\n"
        "    data: { labels: labels, datasets: datasets },\n"
        "    options: {\n"
        "      responsive: true,\n"
        "      maintainAspectRatio: false,\n"
        "      interaction: { mode: 'index', intersect: false },\n"
        "      plugins: {\n"
        "        legend: { display: false },\n"
        "        tooltip: {\n"
        "          backgroundColor: dark ? '#1a1a1a' : '#fff',\n"
        "          titleColor: dark ? '#eee' : '#111',\n"
        "          bodyColor: dark ? '#ccc' : '#444',\n"
        "          borderColor: dark ? '#333' : '#e0e0e0',\n"
        "          borderWidth: 1,\n"
        "          padding: 10,\n"
        "          callbacks: {\n"
        "            label: function(ctx){\n"
        "              if(ctx.dataset.label === 'Objetivo 80%') return null;\n"
        "              var inc = ctx.dataset._incumple ? ctx.dataset._incumple[ctx.dataIndex] : null;\n"
        "              var line = ' ' + ctx.dataset.label + ': ' + ctx.parsed.y + '%';\n"
        "              if(inc !== null) line += ' (' + inc + ' incumple)';\n"
        "              return line;\n"
        "            }\n"
        "          }\n"
        "        }\n"
        "      },\n"
        "      scales: {\n"
        "        x: {\n"
        "          grid: { color: gridColor },\n"
        "          ticks: { color: textColor, font: { family: 'Arial', size: 10 } }\n"
        "        },\n"
        "        y: {\n"
        "          min: 0, max: 100,\n"
        "          grid: { color: gridColor },\n"
        "          ticks: {\n"
        "            color: textColor, font: { family: 'Arial', size: 10 },\n"
        "            callback: function(v){ return v + '%'; }\n"
        "          }\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  };\n"
        "}\n"
        "\n"
        "function drawChart(){\n"
        "  var data = activeDays > 0 ? CHART_DATA.slice(-activeDays) : CHART_DATA;\n"
        "  var ctx = document.getElementById('sla-chart');\n"
        "  if(!ctx) return;\n"
        "  if(slaChart){ slaChart.destroy(); slaChart = null; }\n"
        "  if(data.length === 0) return;\n"
        "  slaChart = new Chart(ctx, buildChartConfig(data));\n"
        "}\n"
        "\n"
        "document.querySelectorAll('.chart-mode-btn').forEach(function(btn){\n"
        "  btn.addEventListener('click',function(){\n"
        "    document.querySelectorAll('.chart-mode-btn').forEach(function(b){b.classList.remove('active');});\n"
        "    this.classList.add('active');\n"
        "    chartMode=this.dataset.mode;\n"
        "    var cc=document.getElementById('cola-controls');\n"
        "    if(cc)cc.style.display=chartMode==='colas'?'flex':'none';\n"
        "    drawChart();\n"
        "  });\n"
        "});\n"
        "\n"
        "document.querySelectorAll('.chart-filter-btn').forEach(function(btn){\n"
        "  btn.addEventListener('click',function(){\n"
        "    document.querySelectorAll('.chart-filter-btn').forEach(function(b){b.classList.remove('active');});\n"
        "    this.classList.add('active');\n"
        "    activeDays=parseInt(this.dataset.days)||0;\n"
        "    drawChart();\n"
        "  });\n"
        "});\n"
        "\n"
        "document.querySelectorAll('.cola-toggle-btn').forEach(function(btn){\n"
        "  var key=btn.dataset.cola;\n"
        "  var onColor=COLA_COLORS[key];\n"
        "  btn.addEventListener('click',function(){\n"
        "    visibleColas[key]=!visibleColas[key];\n"
        "    if(visibleColas[key]){\n"
        "      this.style.borderColor=onColor;\n"
        "      this.style.color=onColor;\n"
        "      this.classList.remove('off');\n"
        "    } else {\n"
        "      this.style.borderColor='#ccc';\n"
        "      this.style.color='#ccc';\n"
        "      this.classList.add('off');\n"
        "    }\n"
        "    drawChart();\n"
        "  });\n"
        "});\n"
        "\n"
        "// Redibujar al cambiar tema para actualizar colores\n"
        "document.getElementById('mo-theme-btn') && document.getElementById('mo-theme-btn')\n"
        "  .addEventListener('click', function(){ setTimeout(drawChart, 50); });\n"
        "\n"
        "drawChart();\n"
    )

    global_html = f"""<!DOCTYPE html>
<html lang="es" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BOST · SLA Global Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --mo-orange:#FF5900; --mo-yellow:#FFD600;
      --mo-black:#000000;  --mo-white:#FFFFFF; --mo-gray:#F2F2F2;
      --mo-text:#111;      --mo-muted:#666;    --mo-border:#e0e0e0;
      --nav-h:56px;
    }}
    [data-theme="dark"] {{
      --mo-gray:#1a1a1a; --mo-text:#f0f0f0; --mo-muted:#aaa;
      --mo-border:#333;  --mo-white:#111;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:Arial,Helvetica,sans-serif; background:var(--mo-gray); color:var(--mo-text); }}

    /* NAV */
    .mo-nav {{
      position:sticky; top:0; z-index:100;
      background:#000; height:var(--nav-h);
      display:flex; align-items:center; justify-content:space-between;
      padding:0 24px; gap:16px;
    }}
    .mo-nav-left {{ display:flex; align-items:center; gap:20px; }}
    .mo-nav-brand {{ color:#fff; font-weight:700; font-size:0.9rem; white-space:nowrap; }}
    .mo-nav-links {{ list-style:none; display:flex; gap:4px; }}
    .mo-nav-links li a {{
      color:#ccc; text-decoration:none; font-size:0.82rem; font-weight:600;
      padding:6px 14px; border-radius:4px; transition:background .15s,color .15s;
    }}
    .mo-nav-links li a:hover {{ background:rgba(255,255,255,.1); color:#fff; }}
    .mo-nav-links li a.active {{ background:var(--mo-orange); color:#fff; }}
    .mo-nav-links li a.disabled {{ color:#555; cursor:not-allowed; pointer-events:none; }}
    .mo-logo {{ width:64px; height:auto; color:#fff; flex-shrink:0; }}

    /* HERO */
    .hero {{
      background:#000; padding:32px 24px 28px;
      display:flex; flex-wrap:wrap; align-items:center;
      justify-content:space-between; gap:16px;
    }}
    .hero-title {{ color:#fff; font-size:1.75rem; font-weight:700; }}
    .hero-sub {{ color:#aaa; font-size:0.85rem; margin-top:4px; }}
    .hero-pill {{
      padding:6px 16px; border-radius:20px; font-size:0.85rem;
      font-weight:700; color:#fff;
      background:{estado_color};
    }}

    /* KPI GLOBAL */
    .kpi-global-block {{
      background:var(--mo-white); border-radius:8px; margin:20px 20px 0;
      padding:20px 24px; display:flex; align-items:center; gap:24px;
      border-left:5px solid {color_global};
      box-shadow:0 1px 4px rgba(0,0,0,.06);
    }}
    .kpi-global-number {{ font-size:2.8rem; font-weight:700; color:{color_global}; line-height:1; }}
    .kpi-global-label {{ font-size:0.9rem; color:var(--mo-muted); }}
    .kpi-global-detail {{ font-size:0.8rem; color:var(--mo-muted); margin-top:3px; }}

    /* COLA CARDS */
    .cards-grid {{
      display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
      gap:14px; padding:14px 20px;
    }}
    .kpi-card {{
      background:var(--mo-white); border-radius:8px; padding:16px 18px;
      box-shadow:0 1px 4px rgba(0,0,0,.06);
    }}
    .kpi-card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
    .kpi-card-label {{ font-weight:700; font-size:0.85rem; }}
    .kpi-card-sla {{ font-size:0.72rem; color:var(--mo-muted); }}
    .kpi-card-pct {{ font-size:1.9rem; font-weight:700; line-height:1; margin-bottom:10px; }}
    .kpi-bar-bg {{ background:#f0f0f0; border-radius:3px; height:8px; overflow:hidden; margin-bottom:8px; }}
    .kpi-bar-fill {{ height:8px; border-radius:3px; transition:width .4s; }}
    .kpi-card-detail {{ font-size:0.75rem; color:var(--mo-muted); }}

    /* CHART SECTION */
    .section-block {{
      background:var(--mo-white); border-radius:8px; margin:0 20px 14px;
      padding:20px 24px; box-shadow:0 1px 4px rgba(0,0,0,.06);
    }}
    .section-title {{ font-size:1rem; font-weight:700; margin-bottom:4px; }}
    .section-subtitle {{ font-size:0.8rem; color:var(--mo-muted); margin-bottom:16px; }}
    .chart-source {{ font-size:0.73rem; color:var(--mo-muted); margin-top:8px; }}

    /* ANÁLISIS */
    .analisis-list {{ padding-left:18px; }}
    .analisis-list li {{ font-size:0.875rem; color:var(--mo-text); margin-bottom:8px; line-height:1.5; }}

    /* FOOTER */
    .mo-footer {{
      background:#000; color:#aaa; font-size:0.75rem;
      padding:18px 24px; margin-top:24px;
      display:flex; align-items:center; justify-content:space-between; gap:16px;
      flex-wrap:wrap;
    }}
    .mo-footer a {{ color:#FF5900; text-decoration:none; }}
    .mo-footer-links {{ display:flex; gap:16px; }}

    /* THEME TOGGLE */
    .mo-theme-btn {{
      background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.2);
      color:#fff; font-size:0.78rem; border-radius:4px; padding:4px 10px;
      cursor:pointer; display:flex; align-items:center; gap:5px; white-space:nowrap;
    }}
    .mo-theme-btn:hover {{ background:rgba(255,255,255,.15); }}

    @media(max-width:600px) {{
      .cards-grid {{ grid-template-columns:1fr 1fr; }}
      .kpi-global-block {{ flex-direction:column; align-items:flex-start; }}
    }}

    /* CHART FILTERS */
    .chart-filters {{ display:flex; gap:6px; }}
    .chart-filter-btn {{
      background:var(--mo-white); border:1.5px solid var(--mo-border);
      color:var(--mo-muted); font-size:0.75rem; font-weight:700;
      padding:4px 12px; border-radius:4px; cursor:pointer;
      font-family:Arial,Helvetica,sans-serif;
      transition:border-color .15s,color .15s,background .15s;
    }}
    .chart-filter-btn:hover {{ border-color:var(--mo-orange); color:var(--mo-orange); }}
    .chart-filter-btn.active {{ background:var(--mo-orange); border-color:var(--mo-orange); color:#fff; }}
    /* COLA TOGGLES */
    .cola-toggle-btn {{
      background:var(--mo-white); border:1.5px solid; font-size:0.72rem; font-weight:700;
      padding:3px 10px; border-radius:4px; cursor:pointer;
      font-family:Arial,Helvetica,sans-serif; transition:opacity .15s;
    }}
    .cola-toggle-btn.off {{ border-color:#ccc !important; color:#ccc !important; }}
    /* CHART MODE */
    .chart-mode-btn {{
      background:var(--mo-white); border:1.5px solid var(--mo-border);
      color:var(--mo-muted); font-size:0.72rem; font-weight:700;
      padding:3px 10px; border-radius:4px; cursor:pointer;
      font-family:Arial,Helvetica,sans-serif; transition:all .15s;
    }}
    .chart-mode-btn.active {{ background:var(--mo-black); border-color:var(--mo-black); color:#fff; }}
    .chart-mode-btn:hover:not(.active) {{ border-color:var(--mo-orange); color:var(--mo-orange); }}
    /* PRODUCT TABS */
    .product-tab {{
      font-size:0.78rem; font-weight:700; padding:4px 14px; border-radius:4px;
      border:1.5px solid var(--mo-border); cursor:pointer; font-family:Arial,Helvetica,sans-serif;
      background:var(--mo-white); color:var(--mo-muted);
    }}
    .product-tab.active {{ background:var(--mo-black); border-color:var(--mo-black); color:#fff; }}
    .product-tab:disabled {{ opacity:.35; cursor:not-allowed; }}
  </style>
</head>
<body>

<!-- NAV -->
<nav class="mo-nav">
  <div class="mo-nav-left">
    <span class="mo-nav-brand">BOST · SLA Dashboard</span>
    <ul class="mo-nav-links">
      <li><a href="global.html" class="active">Global</a></li>
      <li><a href="fijo.html">Fijo</a></li>
      <li><a href="tv.html" class="disabled" title="Próximamente">TV</a></li>
    </ul>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <button class="mo-theme-btn" id="mo-theme-btn" aria-label="Cambiar tema">
      <span id="mo-theme-icon">☽</span>
      <span id="mo-theme-label">Modo oscuro</span>
    </button>
    <svg class="mo-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" role="img" aria-label="MasOrange">
      <rect x="4"  y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="8"  width="16" height="16" fill="currentColor"/>
      <rect x="20" y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="40" width="16" height="16" fill="currentColor"/>
      <rect x="36" y="24" width="16" height="16" fill="currentColor"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="currentColor" stroke-width="10"/>
    </svg>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div>
    <div class="hero-title">SLA Global</div>
    <div class="hero-sub">{dia_semana}, {fecha_str} &middot; Datos a las 08:30h &middot; Generado {hora_str}h</div>
  </div>
  <div class="hero-pill">{estado_emoji} {estado_label}</div>
</section>

<!-- KPI GLOBAL -->
<div class="kpi-global-block">
  <div class="kpi-global-number">{pct_global_display}</div>
  <div>
    <div class="kpi-global-label">Cumplimiento global SLA</div>
    <div class="kpi-global-detail">{total_computables - total_incumple} cumplen · <strong style="color:{color_global}">{total_incumple} incumplen</strong> · {total_computables} total computables</div>
  </div>
</div>

<!-- CARDS COLAS -->
<div class="cards-grid">
{cards_html}
</div>

<!-- GRÁFICA EVOLUTIVA -->
<div class="section-block">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px">
    <div class="section-title">Evolución del cumplimiento</div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <!-- Producto -->
      <div style="display:flex;gap:5px">
        <button class="product-tab active" disabled title="Producto activo">Fijo</button>
        <button class="product-tab" disabled title="Próximamente">TV</button>
      </div>
      <div style="width:1px;height:20px;background:var(--mo-border)"></div>
      <!-- Periodo -->
      <div class="chart-filters">
        <button class="chart-filter-btn active" data-days="7">Semana</button>
        <button class="chart-filter-btn" data-days="30">Mes</button>
        <button class="chart-filter-btn" data-days="0">Todo</button>
      </div>
    </div>
  </div>
  <!-- Cola toggles -->
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px">
    <span style="font-size:0.7rem;color:var(--mo-muted);font-weight:700;text-transform:uppercase;letter-spacing:.05em">Vista:</span>
    <button class="chart-mode-btn active" data-mode="colas">Por colas</button>
    <button class="chart-mode-btn" data-mode="total">Total</button>
    <div style="width:1px;height:18px;background:var(--mo-border);margin:0 2px"></div>
    <div id="cola-controls" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
      <span style="font-size:0.7rem;color:var(--mo-muted);font-weight:700;text-transform:uppercase;letter-spacing:.05em">Colas:</span>
      <button class="cola-toggle-btn" data-cola="fijo"      style="border-color:#FF5900;color:#FF5900">STFIJO&middot;SGI&middot;GIOR</button>
      <button class="cola-toggle-btn" data-cola="logistica" style="border-color:#9c27b0;color:#9c27b0">Log&iacute;stica</button>
    </div>
  </div>
  <div class="section-subtitle">% cumplimiento diario &middot; Objetivo: 80% (l&iacute;nea amarilla)</div>
  <div style="position:relative;height:240px">
    <canvas id="sla-chart"></canvas>
  </div>
  <div class="chart-source">{fuente_nota}</div>
</div>

<!-- ANÁLISIS -->
<div class="section-block">
  <div class="section-title">Análisis del día</div>
  <ul class="analisis-list" style="margin-top:12px">
    {analisis_html}
  </ul>
</div>

<!-- FOOTER -->
<footer class="mo-footer">
  <div>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 68" width="48" style="color:#fff;vertical-align:middle" aria-label="MasOrange">
      <rect x="4"  y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="8"  width="16" height="16" fill="currentColor"/>
      <rect x="20" y="24" width="16" height="16" fill="currentColor"/>
      <rect x="20" y="40" width="16" height="16" fill="currentColor"/>
      <rect x="36" y="24" width="16" height="16" fill="currentColor"/>
      <circle cx="104" cy="34" r="28" fill="none" stroke="currentColor" stroke-width="10"/>
    </svg>
    <span style="margin-left:10px">Generado automáticamente · BOST MasOrange · {fecha_str} {hora_str}h</span>
  </div>
  <div class="mo-footer-links">
    <a href="fijo.html">Informe Fijo</a>
    <a href="tv.html">TV (próx.)</a>
  </div>
</footer>

<script>
  (function() {{
    var html  = document.documentElement;
    var btn   = document.getElementById('mo-theme-btn');
    var icon  = document.getElementById('mo-theme-icon');
    var label = document.getElementById('mo-theme-label');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var stored = localStorage.getItem('mo-theme');
    var isDark = stored ? stored === 'dark' : prefersDark;
    function applyTheme(dark) {{
      html.setAttribute('data-theme', dark ? 'dark' : 'light');
      icon.textContent  = dark ? '☀' : '☽';
      label.textContent = dark ? 'Modo claro' : 'Modo oscuro';
      localStorage.setItem('mo-theme', dark ? 'dark' : 'light');
    }}
    applyTheme(isDark);
    btn.addEventListener('click', function() {{ isDark = !isDark; applyTheme(isDark); }});
  }})();
  {chart_js}
</script>
</body>
</html>"""

    out = REPORTES_DIR / "global.html"
    out.write_text(global_html, encoding="utf-8")
    return out


def bq_datos_listos(client, tz):
    """
    Verifica que BQ tiene datos del día anterior (FECHA_CARGA = ayer).
    Devuelve True si están listos, False si aún no han cargado.
    """
    import time
    ayer = (datetime.now(tz=tz).date() - __import__('datetime').timedelta(days=1)).isoformat()
    sql = f"""
        SELECT MAX(FECHA_CARGA) AS ultima_carga
        FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
        WHERE FECHA_CARGA >= '{ayer}'
        LIMIT 1
    """
    try:
        rows = list(client.query(sql).result())
        ultima = rows[0].ultima_carga if rows else None
        return str(ultima) == ayer
    except Exception as e:
        print(f"[BQ] Error verificando carga: {e}")
        return False


def esperar_datos_bq(client, tz, hora_limite=10, minutos_limite=30, intervalo_min=15):
    """
    Espera hasta que BQ tenga los datos del día anterior o se alcance la hora límite.
    Reintenta cada `intervalo_min` minutos.
    Devuelve True si los datos están listos, False si se agotó el tiempo.
    """
    import time
    while True:
        now = datetime.now(tz=tz)
        if bq_datos_listos(client, tz):
            print(f"[BQ] Datos del día anterior confirmados en BQ.")
            return True

        limite = now.replace(hour=hora_limite, minute=minutos_limite, second=0, microsecond=0)
        if now >= limite:
            print(f"[BQ] {now.strftime('%H:%M')}h — datos aún no disponibles y se alcanzó el límite ({hora_limite:02d}:{minutos_limite:02d}h).")
            return False

        proxima = min(now.timestamp() + intervalo_min * 60, limite.timestamp())
        espera = int(proxima - now.timestamp())
        print(f"[BQ] Datos no disponibles aún. Reintento en {espera // 60} min (límite {hora_limite:02d}:{minutos_limite:02d}h)...")
        time.sleep(espera)


def main():
    tz = ZoneInfo("Europe/Madrid")
    now = datetime.now(tz=tz)

    # Guard anti-duplicado: si el informe de hoy ya existe, no volver a generar
    # (evita doble envío cuando el trigger de logon dispara después del trigger horario)
    REPORTES_DIR.mkdir(exist_ok=True)
    informe_hoy = REPORTES_DIR / f"informe_{now.strftime('%Y-%m-%d')}.html"
    if informe_hoy.exists():
        print(f"[SKIP] Informe de hoy ya generado: {informe_hoy.name} -- nada que hacer.")
        return

    print(f"INFORME SLA FIJO -- {now.strftime('%Y-%m-%d %H:%M')} (Madrid)")
    REPORTES_DIR.mkdir(exist_ok=True)

    client = bigquery.Client(project=PROJECT_ID)

    # Verificar que BQ tiene los datos del día anterior antes de continuar
    if not esperar_datos_bq(client, tz):
        asunto_aviso = f"[AVISO] Informe SLA Fijo {now.strftime('%d/%m/%Y')} — datos BQ no disponibles"
        cuerpo_aviso = (
            f"<p>El informe SLA Fijo del {now.strftime('%d/%m/%Y')} <strong>no se ha podido generar</strong> "
            f"porque los datos de BigQuery no estaban disponibles a las 10:30h.</p>"
            f"<p>Puede deberse a un retraso en la ETL. Revisar con el equipo de datos.</p>"
        )
        try:
            import win32com.client as _win32
            outlook = _win32.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = MAIL_TO
            mail.Subject = asunto_aviso
            mail.HTMLBody = cuerpo_aviso
            mail.Send()
            print(f"[email] Aviso de datos no disponibles enviado a {MAIL_TO}")
        except Exception as e:
            print(f"[email] No se pudo enviar aviso: {e}")
        return

    results = {}
    for sec in SECCIONES:
        sql_path = SCRIPT_DIR / sec["file"]
        print(f"  . {sec['file']} ...", end=" ", flush=True)
        rows = run_query(client, sql_path)
        results[sec["key"]] = rows
        incumple = len([r for r in rows if r.get("estado_sla") == "INCUMPLE"])
        print(f"{len(rows)} tickets ({incumple} INCUMPLE)")

    # Fusionar stfijo+sgi+gior en una sola sección de visualización
    results["fijo"] = sorted(
        results.get("stfijo", []) + results.get("sgi", []) + results.get("gior", []),
        key=lambda r: -(r.get("horas_sin_gestion") or 0)
    )

    # Guard: si BQ no cargó hoy (fin de semana sin ETL), no generar informe vacío
    total_tickets = sum(len(v) for v in results.values())
    if total_tickets == 0:
        print("[AVISO] Sin datos en BQ para hoy -- posible dia sin carga ETL. No se genera informe.")
        return

    print("  . Generando HTML Fijo ...", end=" ", flush=True)
    html = generate_html(results, now)

    out = REPORTES_DIR / f"informe_{now.strftime('%Y-%m-%d')}.html"
    out.write_text(html, encoding="utf-8")
    # Alias permanente para la navegación web
    (REPORTES_DIR / "fijo.html").write_text(html, encoding="utf-8")
    print("OK")
    print(f"  Informe Fijo guardado: {out}")

    # ── Global Dashboard con histórico real ───────────────────────────
    print("  . Cargando histórico ...", end=" ", flush=True)
    historico = cargar_historico(dias=14)
    print(f"{len(historico)} días disponibles")

    print("  . Generando global.html ...", end=" ", flush=True)
    global_out = generar_global_html(results, now, historico)
    print(f"OK  -> {global_out}")

    # Envío email L-V (el script corre L-D para tener KPI diario, pero solo se envía en días laborables)
    if now.weekday() < 5:  # 0=lunes … 4=viernes
        asunto = f"Informe SLA Fijo — {now.strftime('%d/%m/%Y')} — {now.strftime('%H:%M')}h"
        enviar_email(asunto, out, results, now)

        # BST-13236 (Predicción SLA): DESCARTADO 2026-06-12
        # BQ carga estados con ~33h de desfase (snapshot 00:00 del día anterior).
        # Un ticket resuelto ayer tarde no aparece resuelto en BQ hasta mañana.
        # Cualquier umbral de alerta generaría demasiados falsos positivos.
        # La limitación es estructural — no resoluble sin cambiar la fuente de datos.
    else:
        print(f"[email] Fin de semana — KPI registrado, email no enviado")


if __name__ == "__main__":
    main()
