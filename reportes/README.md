# BOST SLA Dashboard

Dashboard diario de seguimiento del SLA de tickets sin gestión para el equipo BOST (BackOffice Servicio Técnico) de MasOrange.

Publicado automáticamente cada día laborable en GitHub Pages.

## Páginas

| Página | Descripción |
|--------|-------------|
| [**Global**](https://samuelminguez-hue.github.io/bost-sla/global.html) | Vista consolidada con navegación a todas las secciones |
| [**Fijo**](https://samuelminguez-hue.github.io/bost-sla/fijo.html) | Tickets FTTH/SAT2 sin gestión — SLA 24h laborables |
| [**TV**](https://samuelminguez-hue.github.io/bost-sla/tv.html) | Tickets SATN2-ZL sin gestión — SLA 24h laborables |
| [**OPITs**](https://samuelminguez-hue.github.io/bost-sla/opits.html) | Tickets con OPIT vinculado activo — Fijo y TV |

## Qué mide

- Tickets activos en colas SAT2 (Fijo) y SATN2-ZL (TV) de MasOrange
- Horas laborables sin gestión desde que el ticket es responsabilidad del equipo
- SLA: 24 horas laborables (08:00–00:00, 7 días/semana)
- KPI de cumplimiento por sección (STFIJO, Logística, TV, etc.)
- OPITs vinculados con más de 5 o 10 días abiertos

## Actualización automática

El informe se genera y publica diariamente a las **09:00h** (lunes a viernes) mediante:

1. `informe_sla_fijo.py` — genera `fijo.html` + `global.html` y envía el email diario
2. `generar_tv_preview.py` — genera `tv.html` + `opits.html`
3. `ejecutar_informe.ps1` — orquesta ambos scripts y hace el push a GitHub Pages

Los datos provienen de BigQuery (`mm-operaciones-bigquery.datastudio.ZZ_averias`), cargados diariamente por el pipeline de datos de MasOrange.

## Estructura del repo

```
reportes/
├── index.html          # Redirección automática a fijo.html
├── global.html         # Dashboard global con navegación
├── fijo.html           # Informe Fijo (regenerado diariamente)
├── tv.html             # Informe TV (regenerado diariamente)
├── opits.html          # Informe OPITs (regenerado diariamente)
└── informe_YYYY-MM-DD.html   # Histórico de informes diarios
```

## Acceso

Dashboard accesible en: **https://samuelminguez-hue.github.io/bost-sla/**

> Repo de uso interno BOST. Los datos son operativos y de acceso restringido al equipo.
