@echo off
:: ============================================================
:: ejecutar_informe.bat
:: Wrapper para Task Scheduler — Informe SLA Fijo (BST-13120)
:: Se ejecuta diariamente a las 09:00h (L-D)
:: ============================================================

set PYTHON=C:\Users\samuel.minguez\AppData\Local\Programs\Python\Python312\python.exe
set SCRIPT=C:\Users\samuel.minguez\OneDrive - MASORANGE\Archivos de José Ramón Vigil Blanco - Proyectos\BOST_AVERIAS_IA\INFORME_SLA_FIJO\informe_sla_fijo.py
set LOG=C:\Users\samuel.minguez\OneDrive - MASORANGE\Archivos de José Ramón Vigil Blanco - Proyectos\BOST_AVERIAS_IA\INFORME_SLA_FIJO\reportes\informe_sla.log

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo Ejecucion: %DATE% %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"
"%PYTHON%" "%SCRIPT%" >> "%LOG%" 2>&1
echo Codigo salida: %ERRORLEVEL% >> "%LOG%"
