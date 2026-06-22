# Bitácora — CC_INFORME_SLA_FIJO (BST-13120)

---

## 2026-06-22 — Samuel Minguez [BST-13346, BST-13295]

### BST-13346: Mejoras UI/UX dashboard

- **Fix bug Noned** (opits.html): ATC-8213670 mostraba "Noned" en columna Días abierto. Causa: HTML generado con código antiguo antes del check `if dias_raw is not None`. Corregido directamente en opits.html.
- **Búsqueda y filtrado en opits.html**: Input de búsqueda en tiempo real (ATC, OPIT, marca, resumen). Select con OPITs únicos y recuento. Cabeceras de grupo por OPIT generadas via JS. Contador "X de Y tickets" dinámico. Implementado en pestañas TV y Fijo.
- **Gráfica con agregación real (global.html)**: Botón "7 días" (últimos 7 diarios), "Semanas" (agrega por semana, promedio %), "Meses" (agrega por mes), "Todo" (todos sin recorte). Selector de rango de fechas Desde/Hasta con botón limpiar. Subtítulo dinámico por vista.
- Template OPITS_HTML_TEMPLATE en generar_tv_preview.py actualizado para que futuras generaciones incluyan el nuevo diseño.

### Auditoría árbol de tickets

- P2-P7 (BST-13127/29/30/31/32/33) cerrados en Jira — estaban completados pero sin transición.
- Creados 3 nuevos tickets:
  - BST-13345: Integrar TV en informe_sla_fijo.py y email diario
  - BST-13346: Mejoras UI/UX dashboard (este ticket)
  - BST-13347: REPORTING - Validar lógica ILOCALIZABLE en Logística TV (Yenny)
- Comentario de sesión publicado en BST-13295.
- CLAUDE.md actualizado con tabla de tickets completa y estados reales.

### Pendientes tras sesión

- ⬜ BST-13345: Integrar TV en script principal (queries validadas, falta main())
- ⬜ BST-13347: Esperar análisis de Yenny sobre FECHA_INICIO_ILOCALIZABLE en TV
- ⬜ BST-13331: Esperar campos FECHA_RELLAMADA/NUMERO_RELLAMADAS de Yenny
- ⬜ BST-13295: Sección OPIT en global.html (tras integración TV)
- ⬜ Push a GitHub Pages de los cambios de hoy (opits.html, global.html)

---

## 2026-06-19 — Samuel Minguez [BST-13295]

### BST-13295: Implementación REMOTE_LINK_OPIT en OPITs

- `query_opit.sql` reescrita: WHERE ahora incluye `REMOTE_LINK_OPIT IS NOT NULL` además de `ISSUE_OPIT`. Campos unificados con COALESCE (`opit_clave`, `opit_status`, `opit_summary`). Campo `opit_origen` para diagnóstico (ISSUE_OPIT / REMOTE_LINK / AMBOS). OPCBI excluidos por ambos campos de resumen.
- Scope real confirmado en BQ: 433 solo ISSUE_OPIT, 3 solo REMOTE_LINK, 23 ambos → 287 OPITs activos (antes 286).
- `generar_tv_preview.py`: fix lectura `opit_status`/`opit_summary` (alias en minúsculas tras COALESCE). Fix "Noned" en columna Días cuando `FECHA_CREACION_OPIT` es NULL (`dias_raw = None` → mostrar "—" en vez de `f'{None}d'`).
- Publicado en GitHub Pages (commit b454601).

### Corrección masiva tickets BST — reglas Jira reconstruidas

- Detectado: 10 tickets con `customfield_21901` (Servicio Técnico Fijo/Movil/TV) mal puesta → causó auto-asignación de BST-13277 y BST-13278 a Javier Llorente.
- Eliminada categoría de: BST-13272, 13277, 13278, 13289, 13292, 13293, 13294, 13295, 13296, 13297.
- BST-13277 y 13278 reasignados a Samuel. BST-13313 asignado a Samuel.
- Componente IA añadido a BST-13319 y BST-13321 (estaban sin componente).
- BST-13331 (Yenny): corregido con epic BST-13120, componentes IA+REPORTING, categoría y asignado a Yenny.
- Memoria interna reconstruida: `feedback_jira_tickets.md` (reglas completas) + `reference_epicas_bst.md` (tabla épicas activas).

### Pendientes tras sesión

- Revisar lógica gestión Logística TV (FECHA_INICIO_ILOCALIZABLE vs etiquetas) — pendiente ticket concreto de logística para análisis.
- Esperar campos FECHA_RELLAMADA / NUMERO_RELLAMADAS de Yenny (BST-13331).
- Integrar TV en email diario informe_sla_fijo.py cuando validación completa.

---

## 2026-06-18 — Samuel Minguez [BST-13295]

### Validación FSM_STATUS en TV (BST-13293)

- Validado con datos reales de ZZ_averias: FSM_STATUS tiene valores CITADA (23 activos) y PENDIENTE CITA (19 activos) en TV
- La lógica de exclusión de Fijo aplica igual en TV → TODO en `query_tv_base.sql` resuelto ✅
- Eliminado TODO del código pendiente de validación FSM_STATUS

### BST-13295: Análisis OPIT en ZZ_averias

- Confirmado que ZZ_averias ya contiene todos los campos OPIT embebidos (ISSUE_OPIT, OPIT_STATUS, OPIT_SUMMARY, fechas CREACION/ASIGNACION/RESOLUCION, PRIO_OPIT, TGJIRA_OPIT, ERROR_101_CON_OPIT)
- No hace falta cruzar con JiraNext para datos OPIT
- Prefijos identificados: TTV- (TV), PROV- (Fijo), MYS-
- Propuesta aprobada: nueva pestaña "OPITs activos" en global.html dividida en TV y Fijo. Tabla: ticket TGJira, OPIT vinculado, estado, días abierto, alerta reclamación (>5d 🟡, >10d 🔴). Tickets con OPIT siguen computando en SLA.
- Comentario publicado en BST-13295 con hallazgos y propuesta

### Protección contra desinstalación de Claude

- Reinstalación identificada como Squirrel auto-updater (no IT policy)
- Creado `~/.claude/scripts/backup-claude.ps1` — backup diario de `~/.claude` a OneDrive `DATA/backup-claude/`
- Registrada tarea `BOST_BackupClaude` en Task Scheduler (diaria 08:50)
- Descargado instalador a `OneDrive/.../DATA/Claude-Setup-x64.exe`
- Modificado `~/.claude/abrir-proyectos.bat` para verificar existencia de claude.exe antes de lanzar

### Pendientes tras sesión

- ⬜ BST-13295: implementar pestaña OPIT en global.html (tras validación queries TV)
- ⬜ BST-13293/13294: validar queries TV con datos reales post-09:00 (cola por cola, árbol igual que Fijo)
- ⬜ Validar FECHA_ULTIMA_ENTRADA_SAT2 en TV — puede requerir ticket Yenny (REPORTING) si no se rellena en transiciones desde Agile_TV_S1/BackOffice hacia SATN2-ZL
- ⬜ Integrar queries TV en `informe_sla_fijo.py` cuando validaciones OK
- ⬜ BST-13143: confirmar proyecto GCP para desplegar Cloud Run

---

## 2026-06-17 — Samuel Minguez [BST-13293, BST-13294]

### BST-13133: Intervalo reintentos BQ — 30 → 15 min

- Cambiado en `informe_sla_fijo.py` el intervalo de reintento de carga BQ de 30 a 15 min
- Pusheado a GitHub (commit `656ba47`)

### Fix Task Scheduler + bug bq_datos_listos

- Corregido encoding del PS1 que impedía la ejecución por Task Scheduler
- Corregido bug en función `bq_datos_listos()` que impedía la verificación correcta de datos
- Informe ejecutado y generado correctamente a las 10:08h (commit `2d0ed22`)

### Fix GitHub Pages + URL + botón dashboard en email

- Añadido botón de acceso al dashboard en el cuerpo del email
- Corregida URL raíz: redirect de `bost-sla/fijo.html` → `reportes/fijo.html` via `index.html`
- Commits: `6dbb2e7`, `1a45eaa`

### Fixes JS/CSS en dashboard fijo.html y global.html

- Fix filtro >96h: ocultaba incorrectamente las filas de otros-row expandidas
- Fix CSV: descarga con `appendChild` en lugar de método que fallaba en Chrome
- Fix logo global + corrección SyntaxError JS (newline literal en `join()` rompía el script)
- Commits: `c9eba65`, `315d113`, `4fb6b86`

### BST-13293: TV P2 — Query base TGJIRA-SATN2-ZL

- Creado `query_tv_base.sql` — lógica TV equivalente a `query_base_p2.sql` de Fijo
- Cola: `TGJIRA-SATN2-ZL`, `TIPO_SERVICIO='TV'`
- Marcas excluidas (BST-13292): EUSKALTEL / R / RACCTEL / TELECABLE / VIRGIN TELCO
- Colas de escalado excluidas: TGJIRA-BACKOFFICE-NTT/JZZ, TGJIRA-AGILE_TV_S1, TGJIRA-ORANGE_TV_S1
- Excepción AGENDADO PRUEBAS heredada de Fijo. Excepción FSM_STATUS (CITADA/PENDIENTE CITA) incluida pendiente validación
- **Pendiente (TODO en código)**: validar si FSM_STATUS tiene lógica de exclusión real en TV — en Fijo excluye cuando contrata tiene cita activa, en TV FSM está casi siempre relleno → verificar con datos reales (ATC-8534234 u otro)
- Pusheado a GitHub

### BST-13294: TV P3 — Logística TV

- Creado `query_tv_logistica.sql` — lógica TV para `TGJIRA-LOGISTICA_ST`
- Labels TV confirmadas en BQ:
  - Inicio (no computan): `#PENDIENTE_SWAP`, `#SWAP_SOLO_MANDO`
  - SAT2 responsable: `#EQUIPO_ENTREGADO`, `#DEVUELTO_ALMACEN`, `#INCIDENCIA_TRANSPORTE`
  - `#SMS_SWAP_ENTREGADO` → tratado igual que `#EQUIPO_ENTREGADO` (automatismo que falla a veces)
  - Sin label: avería normal, SAT2 responsable 24h desde creación/N2
- Lógica CLIENTE ILOCALIZABLE y excepción AGENDADO PRUEBAS heredadas de Fijo
- Pusheado a GitHub
- **Pendiente**: integrar en `informe_sla_fijo.py` (añadir sección TV en `SECCIONES` y `DISPLAY_SECCIONES`) y validar con datos reales

### Pendientes tras sesión

- ⬜ BST-13293: validar FSM_STATUS en TV con datos reales antes de integrar en script
- ⬜ BST-13295: análisis TGJIRA-OPIT (cola compartida Fijo+TV — pendiente entender lógica)
- ⬜ Integrar queries TV en `informe_sla_fijo.py` cuando validaciones OK
- ⬜ BST-13143: confirmar proyecto GCP para desplegar Cloud Run

---

## 2026-06-16 — Samuel Minguez [BST-13133]

### BST-13133: Control de carga BQ antes de generar informe

- Implementadas funciones `bq_datos_listos()` y `esperar_datos_bq()` en `informe_sla_fijo.py`
- Verifica `MAX(FECHA_CARGA) = ayer` antes de continuar. Si no hay datos, reintenta cada 30 min hasta las 10:30h
- Si se agota el tiempo sin datos, envía aviso por email y termina sin generar informe
- Task Scheduler sin cambios — sigue lanzando a las 09:00h
- **Pendiente**: cambiar intervalo de 30 min a 15 min (mañana)

### BST-13130: Validación lógica SLA logístico — cerrado

- Revisada y confirmada la query `query_logistica.sql`. Flujo de labels correcto
- SLA de 24h validado: corre desde `#EQUIPO_ENTREGADO`, `#DEVUELTO_ALMACEN` o `#INCIDENCIA_TRANSPORTE`
- Fases de inicio (`#CAMBIO_CPE`, `#CAMBIO_FAST5670`, `#CABLEDEALIMENTACION`) y tránsito (`#PEDIDO_EN_VUELO`) no computan — correcto
- **BST-13130 cerrado**

### Nuevo ticket (pendiente crear bajo BST-13131): Mejoras dashboard

- Gráfico SVG estático reemplazado por Chart.js 4.4.3 interactivo en `global.html`
- Filtros por texto y categoría en tablas de `fijo.html`
- Resaltado en rojo de filas con más de 96h sin gestión
- Exportación CSV por sección
- Auto-refresco cada 5 min con cuenta atrás visible
- Implementado en `informe_sla_fijo.py` (generador) y aplicado en HTMLs estáticos. Pusheado a GitHub

### BST-13143: Infraestructura Cloud Run preparada

- Creados `Dockerfile` (nginx sirviendo `reportes/`), `cloudbuild.yaml` y `deploy_cloudrun.sh`
- Acceso configurado con `--no-allow-unauthenticated` — solo cuentas `@masorange.es`
- Variable `TU_PROYECTO_GCP` a sustituir cuando el responsable confirme el proyecto GCP
- Repo GitHub reestructurado: `.git` movido de `reportes/` a raíz del proyecto. Código fuente completo (script Python, queries SQL, ficheros deploy, lanzadores Windows) en raíz. HTMLs en `reportes/`. `.gitignore` añadido
- Todo pusheado a `github.com/samuelminguez-hue/bost-sla`
- **Pendiente**: confirmar proyecto GCP para ejecutar despliegue

---

## 2026-06-15 — Samuel Minguez [BST-13131]

### BST-13131 / BST-13143 / BST-13271 / BST-13277 / BST-13278

- Gráfica de evolución SLA reemplazada por versión interactiva en JS: filtros Semana/Mes/Todo, botones toggle por cola con color propio, filtro producto Fijo/TV preparado
- Task Scheduler BOST_SLA_ServidorWeb recreado con junction path C:\BOST\sla_fijo\reportes (fix encoding igual que el informe)
- FECHA_ULTIMA_LABEL_LOGISTICA implementada en query_logistica.sql (campo entregado por Yenny, BST-13271 cerrada)
- Lógica CLIENTE ILOCALIZABLE en Logística: reloj desde FECHA_REVISION_N2 cuando motivo = CLIENTE ILOCALIZABLE
- Auditoría Logística: 7 tickets validados con datos reales de BQ (BST-13277 cerrada)
- GitHub Pages configurado: repo samuelminguez-hue/bost-sla, push automático en run_sla_informe.bat
- URL permanente: https://samuelminguez-hue.github.io/bost-sla/global.html (BST-13278 + BST-13143 cerrada)

---

## 2026-06-12 — Samuel Minguez [BST-13132]

### BST-13132: P6 Resumen IA — verificación producción + CLAUDE_API_KEY Windows

- Ejecutado script manualmente borrando informe previo para forzar regeneración
- Email recibido correctamente con sección "Análisis IA" visible en naranja
- `CLAUDE_API_KEY` añadida como variable de entorno Windows usuario via `[System.Environment]::SetEnvironmentVariable` — Task Scheduler la heredará automáticamente en nuevas sesiones
- **BST-13132 cerrado** con comentario de verificación

### BST-13236: Predicción SLA — implementado y descartado

- Query `query_prediccion_sla.sql` creada: misma lógica de responsabilidad de query_base_p2.sql, filtro `18h ≤ horas_laborables < 24h`, 3 niveles urgencia (crítico/urgente/atención)
- Funciones `build_email_prediccion()` y `enviar_email_prediccion()` implementadas en script
- Email de prueba enviado: 106 tickets detectados en ventana de riesgo
- **Problema estructural detectado**: BQ tiene ~33h de desfase en estados (snapshot 00:00 del día anterior). Verificado con ATC-8535678 (resuelto jueves 14:01, seguía apareciendo como activo)
- Código revertido del script principal. Comentario explicativo dejado en código. `query_prediccion_sla.sql` queda en repo como artefacto documental
- **BST-13236 cerrado Won't Do** — viable solo con acceso TGJira API en tiempo real

### BST-13220: FECHA_AGENDADO_PRUEBAS verificada

- Yenny confirma campos arreglados
- Verificación BQ: 10 tickets con campo relleno, fechas futuras correctas (15-30 junio), formato timestamp OK
- 11 tickets con campo nulo — comportamiento correcto (sin fecha concreta → cuentan para SLA)
- **P8 desbloqueado — validación programada lunes 16/06**

### BST-13245: Dashboard Operativo Confluence

- Página actualizada a v5 (masorange.atlassian.net pageId 1532952577)
- Añadida sección "Radar Jira Cloud" con 11 tickets abiertos (RED-821/820/819/818, PROV-3505/870, MFEAS-283, ADATLL-869/802/441/278)
- Estado BOST IA actualizado: P6 completado, P8 desbloqueado, BST-13236 descartado
- Nota manual sobre BST-13235 (conversión a Épica no posible via API Jira Server)
- Incidente Atlassian activo durante sesión: Confluence frontend caído, API REST operativa

### BST-13235: Conversión a Épica

- Intento via API REST fallido (restricción instancia Jira Server no permite cambio de tipo)
- Samuel realizó la conversión manualmente desde la web ✅

---

## 2026-06-11 — Samuel Minguez

### BST-13131: Script Python — email v2, nav, ejecución completa

- Rediseño completo del email: cuerpo corto visual (semáforo + barras de progreso por cola + análisis automático 3 puntos) + HTML completo como adjunto
- `build_email_body()` implementada. `enviar_email()` actualizado para recibir `results` y `now`
- `fijo.html` generado como alias permanente en cada ejecución (navegación web)
- Nav conectada fijo.html ↔ global.html con tabs activos
- Fix unicode: `→` en print incompatible con cp1252 Windows → cambiado a `->`
- Ejecución manual completa exitosa: 1.230 tickets STFIJO (413 INCUMPLE), 1 SGI, 0 GIOR, 316 Logística (182 INCUMPLE). Email enviado a samuel.minguez@masorange.es

### BST-13133: P7 — Task Scheduler creado

- Creado Task Scheduler Windows `BOST_SLA_Informe_Fijo` via `schtasks.exe`
- Configuración: L-V a las 09:00h, Python 3.12 (`AppData\Local\Programs\Python\Python312\python.exe`)
- Directorio de trabajo: INFORME_SLA_FIJO/. Estado: "Listo". Próxima ejecución: 12/06/2026 09:00h
- Log dir: `C:\Users\samuel.minguez\AppData\Local\BOST_SLA\`
- P7 completado

### BST-13142: Histórico puente — SVG con datos reales

- Implementadas 3 funciones en `informe_sla_fijo.py`:
  - `extraer_kpis_de_html(path)`: extrae pct e incumple de cada cola via regex del HTML generado
  - `cargar_historico(dias=14)`: escanea reportes/ buscando `informe_YYYY-MM-DD.html`
  - `generar_global_html(results, now, historico)`: genera global.html con SVG real (4 líneas de color + target 80% amarillo punteado)
- Integrado en `main()`: carga histórico → genera global.html automáticamente tras fijo.html
- Probado: 2 días disponibles (10/06 stfijo=71.2%, 11/06 stfijo=70.2%)
- Solución temporal hasta que BST-13142 tenga tabla BQ oficial

### BST-13143: Global Dashboard — datos reales en producción

- `generar_global_html()` integrada en `main()` — global.html regenerado en cada ejecución
- Dashboard completo: hero negro con semáforo, KPI global con borde-color, 4 cards de colas, SVG histórico real, análisis automático, dark mode, footer con links
- Verificado en preview: fijo.html ↔ global.html navegación bidireccional operativa

### BST-13134: P8 — Validación campos Yenny + lógica de negocio

- Verificados en BQ los campos FECHA_AGENDADO_PRUEBAS y FECHA_INICIO_ILOCALIZABLE
- FECHA_AGENDADO_PRUEBAS: campo incorrecto — contiene timestamp de actualización, NO la fecha de cita real. Validado con ATC-8501430 (BQ: 05/jun, Jira: 12/jun) y ATC-8503395 (BQ: 06/jun, Jira: 15/jun)
- FECHA_INICIO_ILOCALIZABLE: solo rellena en tickets CANCELADOS/CERRADOS — inútil para activos
- Lógica confirmada con Samuel: ILOCALIZABLE sin excepción (cuenta desde última N2). AGENDADO PRUEBAS: excepción solo si cita futura, si pasó INCUMPLE
- APPOINMENT_DATE → FECHA_AGENDADO_PRUEBAS actualizado en las 4 SQLs. Condición CURRENT_DATE() → CURRENT_TIMESTAMP()
- Validación tickets ILOCALIZABLE: ATC-8494548 (100.1h), batch 08/jun 52.4h — lógica correcta

### BST-13220: REPORTING — Bug FECHA_AGENDADO_PRUEBAS reportado a Yenny

- Verificación completa en BQ: campo no contiene fecha de cita real
- Publicado comentario a Yenny (id: 8655793) con tabla de 3 ejemplos (ATC-8501430, ATC-8503395, ATC-8494548) explicando diferencia entre valor BQ y cita real Jira
- APPOINMENT_DATE también NULL en los 3 tickets → ningún campo BQ tiene la fecha correcta

### BST-13235/36/37/38: AI use cases BOST

- 4 tickets creados (sesión anterior): BST-13235 épica raíz + BST-13236/37/38 análisis de casos de uso
- Pendiente: enlazar 13236/37/38 a 13235 en Jira

---

## 2026-06-10 — Samuel Minguez

### BST-13127: Query base — lógica MAX con FECHA_ULTIMA_ENTRADA_SAT2

- Integrado campo FECHA_ULTIMA_ENTRADA_SAT2 (BST-13215, Yenny) en query_base_p2.sql
- Primera versión usaba COALESCE: cogía FSM/FRANQ si existía aunque fuera más antigua que FECHA_ULTIMA_ENTRADA_SAT2 → horas infladas
- Corregido con MAX sobre todos los campos de fecha: FSM, FRANQUEADA, GIOR, EXTERNO, ENTRADA_SAT2, CREACION → siempre gana la más reciente
- Validado con ATC-8365058 (553h→86h) y ATC-8454373 (280h→218h). origen_reloj actualizado
- Aclaración clave: 2.736 de 2.790 tickets tienen FECHA_ULTIMA_ENTRADA_SAT2=NULL porque nunca salieron de STFIJO-ZL → FECHA_CREACION es correcto para ellos

### BST-13133: Email Outlook COM operativo

- Añadida función enviar_email() a informe_sla_fijo.py (patrón idéntico a DAILY_REPORT)
- Envío solo L-V; KPI registrado L-D (script corre 7 días)
- Guard implementado: si total_tickets == 0 → no generar HTML ni enviar email (protección fin de semana sin ETL)
- MAIL_TO = samuel.minguez@masorange.es (prueba). Destinatarios finales pendientes
- Email de prueba enviado y recibido correctamente a las 15:00h
- Identificado helper personal: ~/.claude/jira-personal.sh con JIRA_PAT_SAMUEL → usarlo siempre en lugar del token de Joseramon

### BST-13215: FECHA_ULTIMA_ENTRADA_SAT2 — entregado y cerrado

- Campo verificado en BQ y funcional. Marcado como ✅ Entregado en CLAUDE.md

### BST-13220: Nuevo ticket Yenny — FECHA_AGENDADO_PRUEBAS + FECHA_INICIO_ILOCALIZABLE

- Detectado durante revisión ATC-8459093: APPOINMENT_DATE = cita de contrata FSM, no fecha de agendamiento interno
- Necesarios dos campos distintos:
  - FECHA_AGENDADO_PRUEBAS: valor del campo Jira "Fecha y Hora de Acción Pendiente" cuando motivo = AGENDADO PRUEBAS (fecha futura de cita con cliente)
  - FECHA_INICIO_ILOCALIZABLE: timestamp del cambio de estado a Ilocalizable (límite 24h desde ese momento)
- Ticket creado BST-13220 + comentario de corrección publicado
- Hasta entrega de este campo, las excepciones AGENDADO PRUEBAS e ILOCALIZABLE no se pueden implementar correctamente

### BST-13134: Validación P8 — parcial

- ATC-8448104: falso positivo operativo, ya corregido
- ATC-8459093: bug APPOINMENT_DATE → origen de BST-13220
- ATC-8421062: PENDIENTE LOGISTICA en STFIJO-ZL, medición ~166h correcta (desde 3/jun)
- Revisión pausada hasta BST-13220

---

## 2026-06-09 — Samuel Minguez (sesión Cowork)

### BST-13140: Bug FECHA_ULTIMA_LABEL_GIOR confirmado resuelto

- Verificado en BQ (FECHA_CARGA = 2026-06-09): ATC-8494595 tiene FECHA_ULTIMA_LABEL_GIOR = 2026-06-07 ✅
- Tickets activos GIOR: 2 con GIOR_ENCURSO (Vodafone) → NULL correcto y esperado
- Comentario publicado en BST-13140 avisando a Yenny. Ticket cerrado.
- query_gior.sql ya puede usar FECHA_ULTIMA_LABEL_GIOR con confianza

**Próxima sesión:** Arrancar P5 — script Python que combina las 4 queries + genera HTML del informe.

---

## 2026-06-08 (tarde) — Samuel Minguez (sesión Cowork)

### P4-Logística: query_logistica.sql escrita y validada en BQ

**Análisis previo en BigQuery:**
- TGJIRA-LOGISTICA_ST: cola compartida TV+FIJO — filtro TIPO_SERVICIO='FIBRA' → 238 tickets legítimos
- Labels confirmadas en datos reales: #EQUIPO_ENTREGADO (70), #INCIDENCIA_TRANSPORTE (26), #DEVUELTO_ALMACEN (en INCIDENCIA), #PEDIDO_EN_VUELO (2), SOLO_INICIO (140)
- Sin timestamp de label → inicio_reloj = FECHA_REVISION_N2 ?? FECHA_CREACION

**query_logistica.sql creada y validada:**
- Scope: LOGISTICA_ST + FIBRA + estados activos + no masivas/colectivas/fantasma
- Excluidos: SOLO_INICIO (transportista aún no recoge) y PEDIDO_EN_VUELO (en tránsito)
- Computables: EQUIPO_ENTREGADO + INCIDENCIA_TRANSPORTE + DEVUELTO_ALMACEN → SLA 24h
- Resultado hoy: 94 de 95 tickets computables INCUMPLEN (media 69h, peor 229h en INCIDENCIA_TRANSPORTE)

**Tickets cerrados (rezago):** BST-13127 (P2) y BST-13129 (P3) — completados en sesiones anteriores

**Próxima sesión:** Validar query_logistica.sql con equipo. Confirmar SLA CREAR_GIOR. Arrancar P5.

---

## 2026-06-08 — Samuel Minguez

### P4-GIOR: arquitectura clarificada, query_base_p2.sql corregida, bug Yenny detectado

**Arquitectura GIOR clarificada:**
- TGJIRA-ESCALADO GIOR solo tiene CREAR_GIOR (SAT2 debe crear ticket en Vodafone) y GIOR_ENCURSO (Vodafone gestionando)
- Al ponerse GIOR_GESTIONADO o DISPATCHING_MANUAL, el ticket vuelve automáticamente a TGJIRA-SATN2-STFIJO-ZL
- Estos tickets devueltos ya los captura query_base_p2.sql — solo necesitaba incluir FECHA_ULTIMA_LABEL_GIOR

**Fix query_base_p2.sql:**
- Añadido FECHA_ULTIMA_LABEL_GIOR al SELECT de tickets_scope
- calcular_inicio_reloj: sustituido CASE+GREATEST por UNNEST+MAX sobre [FSM, FRANQUEADA, LABEL_GIOR] — maneja NULLs correctamente, toma siempre la más reciente
- origen_reloj renombrado a 'FSM/FRANQ/GIOR'
- Validado con 4 tickets GIOR devueltos: 3 correctos (ATC-8276407 ✅, ATC-8460533 ✅, ATC-8445400 ✅), 1 afectado por bug Yenny (ATC-8494595)

**query_gior.sql simplificada:**
- Scope reducido a TGJIRA-ESCALADO GIOR con LABELS LIKE '%CREAR_GIOR%'
- Sin FSM/FRANQ/EXTERNO (no aplica en esta cola)
- inicio_medicion: FECHA_REVISION_N2 si existe, sino FECHA_CREACION
- Validada: 1 ticket activo (ATC-8499769, CUMPLE 12.4h lab)
- SLA provisional 24h — pendiente confirmar con negocio

**Bug Yenny (BST-13140):**
- FECHA_ULTIMA_LABEL_GIOR no se actualiza en carga diaria
- ATC-8494595: GIOR_GESTIONADO puesto el 07/06 (domingo) → NULL en carga 08/06
- Comentado en BST-13140 con ticket de prueba y comportamiento esperado

**BST-13171 cerrado:** script session-handoff.sh validado, entorno Cowork↔VS Code operativo

**Próxima sesión:** P4-Logística (análisis fases por labels, SLA por fase). Esperar corrección bug Yenny.

---

## 2026-06-05 — Samuel Minguez

### P4-SGI completado y validado. GIOR bloqueado. Yenny avisada.

**Verificación campos Yenny (BST-13140):**
- FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR, HORA_VUELTA_ESC_EXTERNO_AD_OR, TOTAL_DEVOLUCIONES_EXTERNO_AD_OR: ✅ existen en BQ con datos reales (109 tickets en carga 2026-06-05, proveedores ADAMO/ORANGE/TESA/LYNTIA)
- Descubierto campo ETI_GIOR (INT64, flag 0/1) — no es timestamp, no sirve para SLA
- Solicitado 4º campo: FECHA_ULTIMA_LABEL_GIOR (TIMESTAMP) — comentario publicado en BST-13140, Yenny avisada por privado

**Lógica GIOR confirmada (BST-13130):**
- DISPATCHING_MANUAL → SAT2 responsable
- GIOR_ENCURSO → Vodafone gestionando (excluir)
- GIOR_GESTIONADO → Vodafone devuelve, SAT2 responsable
- El reloj SAT2 arranca desde que se puso la última label GIOR relevante → requiere FECHA_ULTIMA_LABEL_GIOR

**Validación datos hoy (FECHA_CARGA 2026-06-05):**
- STFIJO-ZL: 1.141 tickets, 316 INCUMPLE (27.7%) — estable respecto ayer
- SGI: 6 activos, 4 INCUMPLE (peor: 155h lab sin gestión desde 26/05)
- GIOR: 3 activos, 1 SAT2 (DISPATCHING_MANUAL), 2 Vodafone (GIOR_ENCURSO)

**query_sgi.sql creada y validada (P4-SGI ✅):**
- Cola: TGJIRA-SATN2-STFIJO-SGI
- SLA: 48h laborables (vs 24h de STFIJO-ZL)
- inicio_medicion: FECHA_REVISION_N2 si existe, sino FECHA_CREACION
- Misma fórmula horas laborables (08:00-00:00, 7 días/semana)
- Sin lógica FSM/FRANQ/EXTERNO (SGI no escala a contratas ni externos)

**Próxima sesión:** Esperar FECHA_ULTIMA_LABEL_GIOR de Yenny → implementar P4-GIOR. Arrancar análisis P4-Logística (fases, SLA por fase). Luego P5.

---

## 2026-06-04 — Samuel Minguez

### P2+P3: Query base + horas laborables — Validación y correcciones

**Bugs corregidos en query_base_p2.sql:**
- `NOT (NULL IN lista)` = NULL en BigQuery → excluía 943 tickets incorrectamente del filtro de responsabilidad. Fix: `IS NULL OR NOT IN`
- `GREATEST(timestamp, NULL)` = NULL → tickets con solo FSM o solo FRANQUEADA caían a FECHA_CREACION como inicio del reloj. Fix: CASE + COALESCE anidado
- `tickets_scope` no seleccionaba `FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR` → campo de Yenny no llegaba a los CTEs

**Nuevas funcionalidades incorporadas:**
- P3 completado: horas laborables SAT2 (08:00-00:00, 7 días/semana) via fórmula `(días × 16h) + bh_día(T2) - bh_día(T1)` en zona Europe/Madrid
- Campo Yenny `FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR` integrado como Caso 2 del inicio del reloj (Orange/ADAMO con integración)
- `DEFERRED.AWAITING-CANCELATION` añadido como estado de devolución de externos
- `FECHA_REVISION_N2` como evidencia de gestión N2 (CTE `ajustar_por_gestion_n2`): si el agente actuó después del inicio del reloj, la medición arranca desde esa gestión

**Validación con tickets reales:**
- A (FSM reciente): 3/3 fechas correctas ✅
- B (Yenny EXTERNO_AD_OR): sin histórico aún, esperado ✅
- C (FECHA_CREACION): 3 falsos positivos detectados y corregidos por GESTION_N2 ✅
- D (TESA+contrata): GREATEST correcto, coge última devolución entre ambos ✅

**Decisiones de diseño:**
- FECHA_CREACION como fallback universal (no solo REGISTRADA): tickets FSM='vacio' nunca escalados son medibles desde creación. Limitación documentada para tickets que pasaron por otras colas (SGI, GIOR, Logística, provisiones) — se abordará en P4
- `origen_reloj` expuesto en output: GESTION_N2 / FSM/FRANQ / EXTERNO_AD_OR / FECHA_CREACION
- Dos columnas de fecha separadas: `fecha_inicio_responsabilidad` (cuándo entró en nuestra cola) y `fecha_ultima_gestion` (cuándo actuó el agente N2)

**Resultado final validado:**
- 1.019 tickets en scope
- INCUMPLE: 317 (31%)
- CUMPLE: 702 (69%)
- Origen GESTION_N2: 529 (52%) | FSM/FRANQ: 370 (36%) | FECHA_CREACION: 120 (12%)

**Otros:**
- Confirmado que FECHA_ULTIMA_DEVUELTA_FSM SÍ se rellena para RESUELTA NO OK (solo 3 tickets ANULADA con FSM nulo — edge case, OT cancelada sin devolución formal)
- Campos Yenny en BQ confirmados: FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR (TIMESTAMP), HORA_VUELTA_ESC_EXTERNO_AD_OR (INT64), TOTAL_DEVOLUCIONES_EXTERNO_AD_OR (INT64). Datos históricos pendientes.
- Documentación completa de devoluciones por proveedor comentada en BST-13140
- Lógica Vodafone GIOR por labels documentada en BST-13130
- 10 tickets del proyecto asignados a Samuel (indicación José)
- P2 y P3 cerrados. Próximo: P4 (colas especiales)
