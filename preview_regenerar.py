"""
Script de preview — regenera fijo.html + global.html con el código actual
sin el guard anti-duplicado ni envío de email.
Uso: python preview_regenerar.py
"""
import sys, subprocess
sys.path.insert(0, r'C:\BOST\sla_fijo')

import informe_sla_fijo as m
from google.cloud import bigquery
from zoneinfo import ZoneInfo
from datetime import datetime

tz = ZoneInfo("Europe/Madrid")
now = datetime.now(tz=tz)

print(f"[PREVIEW] {now.strftime('%Y-%m-%d %H:%M')} — regenerando HTML sin email ni guard...")

# BQ client
print("  . Conectando a BigQuery...")
client = bigquery.Client(project=m.PROJECT_ID)

# Queries
results = {}
for sec in m.SECCIONES:
    sql_path = m.SCRIPT_DIR / sec["file"]
    print(f"  . {sec['file']} ...", end=" ", flush=True)
    rows = m.run_query(client, sql_path)
    results[sec["key"]] = rows
    incumple = len([r for r in rows if r.get("estado_sla") == "INCUMPLE"])
    print(f"{len(rows)} tickets ({incumple} INCUMPLE)")

# Merge Fijo = stfijo+sgi+gior, TV = tv_base
results["fijo"] = sorted(
    results.get("stfijo", []) + results.get("sgi", []) + results.get("gior", []),
    key=lambda r: -(r.get("horas_sin_gestion") or 0)
)
results["tv"] = sorted(
    results.get("tv_base", []),
    key=lambda r: -(r.get("horas_sin_gestion") or 0)
)
total = sum(len(v) for k, v in results.items() if k in ("fijo", "logistica", "tv", "tv_logistica"))
print(f"  Total display: {total} tickets")

# fijo.html
print("  . Generando fijo.html ...", end=" ", flush=True)
html = m.generate_html(results, now)
(m.REPORTES_DIR / "fijo.html").write_text(html, encoding="utf-8")
print("OK")

# global.html
print("  . Cargando historico ...", end=" ", flush=True)
historico = m.cargar_historico(dias=14, client=client)
print(f"{len(historico)} dias")

print("  . Generando global.html ...", end=" ", flush=True)
global_out = m.generar_global_html(results, now, historico)
print(f"OK -> {global_out}")

# Git push a GitHub Pages
print("\n[PREVIEW] Subiendo a GitHub Pages...")
repo = r'C:\BOST\sla_fijo'
subprocess.run(['git', '-C', repo, 'add',
                'reportes/fijo.html', 'reportes/global.html'], check=True)
result = subprocess.run(['git', '-C', repo, 'diff', '--cached', '--stat'],
                        capture_output=True, text=True)
print(result.stdout.strip() or "  (sin cambios staged)")

commit = subprocess.run(['git', '-C', repo, 'commit', '-m',
                         'preview: regenerar HTML con fixes 23/06 (filtros, IA key, cola label)'],
                        capture_output=True, text=True)
print(commit.stdout.strip())
if commit.returncode != 0:
    print(commit.stderr.strip())

push = subprocess.run(['git', '-C', repo, 'push'], capture_output=True, text=True)
print(push.stdout.strip())
print(push.stderr.strip())
if push.returncode != 0:
    print("[ERROR] Push falló")
    sys.exit(1)

print("\n[PREVIEW] Listo!")
print("  fijo.html  : https://samuelminguez-hue.github.io/bost-sla/reportes/fijo.html")
print("  global.html: https://samuelminguez-hue.github.io/bost-sla/reportes/global.html")
