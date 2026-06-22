# bost-sla — Informe SLA BOST

Sistema de generación y publicación automática del dashboard diario de SLA para el equipo BOST (BackOffice Servicio Técnico) de MasOrange.

**Dashboard publicado:** https://samuelminguez-hue.github.io/bost-sla/

---

## Qué hace

Cada día laborable a las 09:00h:

1. Consulta BigQuery (`mm-operaciones-bigquery.datastudio.ZZ_averias`) con los tickets activos del día
2. Calcula horas laborables sin gestión por ticket (SLA 24h, 08:00–00:00, 7 días/semana)
3. Genera los HTML del dashboard (Fijo, TV, OPITs, Global)
4. Envía el informe diario por email (Outlook COM)
5. Publica en GitHub Pages vía `git push`

---

## Estructura

```
├── informe_sla_fijo.py       # Script principal — genera fijo.html + global.html + email
├── generar_tv_preview.py     # Genera tv.html + opits.html (TV y OPITs)
├── ejecutar_informe.ps1      # Orquestador PowerShell — lanza ambos scripts + push
├── ejecutar_informe.bat      # Wrapper .bat para Task Scheduler
│
├── query_base_p2.sql         # Query principal Fijo (colas SAT2)
├── query_logistica.sql       # Query Logística Fijo
├── query_gior.sql            # Query cola GIOR (Vodafone, SLA 48h)
├── query_sgi.sql             # Query cola SGI (SLA 48h)
├── query_tv_base.sql         # Query TV (cola SATN2-ZL)
├── query_tv_logistica.sql    # Query Logística TV
├── query_opit.sql            # Query OPITs activos (Fijo + TV)
│
└── reportes/                 # Carpeta publicada en GitHub Pages
    ├── index.html            # Redirección automática a fijo.html
    ├── global.html           # Dashboard global con navegación
    ├── fijo.html             # Informe Fijo (regenerado diariamente)
    ├── tv.html               # Informe TV
    ├── opits.html            # Informe OPITs
    └── informe_YYYY-MM-DD.html  # Histórico
```

---

## Requisitos

- Python 3.x con `google-cloud-bigquery` y credenciales ADC configuradas (`gcloud auth application-default login`)
- Outlook Desktop instalado y configurado con cuenta MasOrange
- Git con acceso al repo (`gh auth login` o PAT configurado)
- Task Scheduler de Windows (tarea `BOST_InformeSLA` — lunes a viernes 09:00h)

---

## Ejecución manual

```powershell
# Ejecutar informe completo (Fijo + TV + push)
& "C:\BOST\sla_fijo\ejecutar_informe.ps1"

# Solo Fijo + email
python informe_sla_fijo.py

# Solo TV + OPITs (sin email)
python generar_tv_preview.py

# Modo prueba — email solo a samuel.minguez@masorange.es
python informe_sla_fijo.py --solo-samuel   # (email interno del equipo)
```

---

## Épica Jira

[BST-13120](https://jiranext.masorange.es/browse/BST-13120) — CC_INFORME_SLA_FIJO
