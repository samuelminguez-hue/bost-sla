# ============================================================
# ejecutar_informe.ps1
# Wrapper para Task Scheduler — Informe SLA Fijo (BST-13120)
# Se ejecuta diariamente a las 09:00h (L-D)
# ============================================================

$python   = "C:\Users\samuel.minguez\AppData\Local\Programs\Python\Python312\python.exe"
$script   = "C:\Users\samuel.minguez\OneDrive - MASORANGE\Archivos de José Ramón Vigil Blanco - Proyectos\BOST_AVERIAS_IA\INFORME_SLA_FIJO\informe_sla_fijo.py"
$log      = "C:\Users\samuel.minguez\OneDrive - MASORANGE\Archivos de José Ramón Vigil Blanco - Proyectos\BOST_AVERIAS_IA\INFORME_SLA_FIJO\reportes\informe_sla.log"
$workdir  = "C:\Users\samuel.minguez\OneDrive - MASORANGE\Archivos de José Ramón Vigil Blanco - Proyectos\BOST_AVERIAS_IA\INFORME_SLA_FIJO"
$git      = "C:\Users\samuel.minguez\AppData\Local\Programs\Git\mingw64\bin\git.exe"
$reportes = "$workdir\reportes"

function Log($msg) { Add-Content -Path $log -Value $msg }

# Cabecera de log
$sep = "=" * 60
$ts  = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Log ""; Log $sep; Log "Ejecucion: $ts"; Log $sep

# ── 1. Generar informe (Python) ───────────────────────────────
Set-Location $workdir
$output = & $python $script 2>&1
$exitPy = $LASTEXITCODE
$output | ForEach-Object { Log $_ }
Log "Codigo salida Python: $exitPy"

if ($exitPy -ne 0) {
    Log "ERROR: Python falló. Abortando git push."
    exit $exitPy
}

# Comprobar si fue un SKIP (ya generado hoy) — no hay nada nuevo que subir
$outputStr = $output -join " "
if ($outputStr -match "\[SKIP\]") {
    Log "Informe ya generado hoy (SKIP). No se hace push."
    exit 0
}

# ── 2. Git push a GitHub Pages ────────────────────────────────
Set-Location $reportes
$fecha = Get-Date -Format "yyyy-MM-dd HH:mm"

& $git add fijo.html global.html 2>&1 | ForEach-Object { Log $_ }

# Solo commitear si hay cambios staged
$status = & $git status --porcelain fijo.html global.html 2>&1
if (-not $status) {
    Log "Git: sin cambios en fijo.html/global.html. No se hace commit."
    exit 0
}

& $git commit -m "Informe diario $fecha" 2>&1 | ForEach-Object { Log $_ }
& $git push origin master:main 2>&1 | ForEach-Object { Log $_ }

if ($LASTEXITCODE -eq 0) {
    Log "GitHub Pages actualizado OK -> https://samuelminguez-hue.github.io/bost-sla/"
} else {
    Log "AVISO: git push fallido (codigo $LASTEXITCODE)"
    exit $LASTEXITCODE
}
