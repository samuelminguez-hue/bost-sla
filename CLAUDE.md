# CC_INFORME_SLA_FIJO — Informe diario de tickets no gestionados (Servicio de Fijo)

**Jira**: BST-13120 | Parent: BST-13103 (CC_BOST_AVERIAS_IA)
**Propietario**: Samuel Minguez

---

## Descripción

Informe diario automatizado que identifica los tickets del servicio de fijo (FIBRA) que llevan más de 24 horas sin gestión bajo responsabilidad del equipo SAT2.

Objetivo: medir y visibilizar el cumplimiento del SLA de gestión interna, diferenciando cuándo el incumplimiento es de SAT2 y cuándo el ticket está activamente en manos de un proveedor o contrata.

---

## ⚠️ MIGRACIÓN JIRA PENDIENTE — jiranext → masorange.atlassian.net (cloud)

**Estado**: análisis en curso (Anna, desde 10/06). Samuel avisará cuando se ejecute.
**Documento**: `https://confluence.nodus.masorange.es/wiki/spaces/ATLAS/pages/1524269204/BST+-+Analisis+de+campos`

**Qué cambia:**

| Elemento | Antes (DC) | Después (Cloud) |
|---|---|---|
| URL Jira | `jiranext.masorange.es` | `masorange.atlassian.net` |
| Auth API | `Bearer PAT` (jira-personal.sh) | API token Atlassian Cloud (MCP ya configurado) |
| IDs ticket | BST-XXXXX (actuales) | Nuevos IDs (hay fichero de mapping old→new) |
| IDs customfields | `customfield_10100`, `customfield_21901`... | Distintos en cloud — verificar tras migración |
| Creación tickets | curl / PowerShell directo | MCP Atlassian ya funciona en cloud |

**Población a migrar**: `project = 'BST' and statusCategory != Done and updated >= startOfYear(-3)` — todos los tickets activos nuestros entran.

**Riesgo detectado**: problemas con adjuntos `.md` en sandbox. Nuestras BITACORA son `.md` — vigilar que migren correctamente.

**Al migrar (checklist):**
1. Obtener el fichero de mapping old→new IDs y actualizar referencias en CLAUDE.md, VALIDACION_P8.md y BITACORA.md
2. Verificar IDs de customfields en cloud: Epic Link, Categoría, Componentes
3. Actualizar sección "Creación de tickets Jira" de este CLAUDE.md con nuevos field IDs y auth
4. El script `jira-personal.sh` y las llamadas curl quedan obsoletos — usar MCP Atlassian directamente
5. Verificar que componentes `IA` y `REPORTING` existen en cloud antes de la carga (deben crearse ANTES del CSV)

---

## Creación de tickets Jira — Campos obligatorios

Al crear cualquier ticket bajo esta épica (BST-13120), siempre incluir:

| Campo | Tickets propios (Samuel) | Tickets REPORTING (Yenny) |
|---|---|---|
| **Epic Link** `customfield_10100` | `BST-13120` | `BST-13120` |
| **Componentes** | `[IA]` | `[IA, REPORTING]` |
| **Categoría** `customfield_21901` id `28300` | `Servicio Tecnico Fijo/Movil/TV` | `Servicio Tecnico Fijo/Movil/TV` |
| **Assignee** | `samuel.minguez@masorange.es` | `yennyestefanny.medin@asesormasmovil.es` |
| **Watcher** | — | `samuel.minguez@masorange.es` |

**Body de creación mínimo (ticket propio):**
```json
{
  "fields": {
    "project": {"key": "BST"},
    "issuetype": {"name": "Tarea"},
    "summary": "...",
    "assignee": {"name": "samuel.minguez@masorange.es"},
    "customfield_10100": "BST-13120",
    "components": [{"name": "IA"}],
    "customfield_21901": {"id": "28300"},
    "description": "..."
  }
}
```

**Body de creación mínimo (ticket REPORTING para Yenny):**
```json
{
  "fields": {
    "project": {"key": "BST"},
    "issuetype": {"name": "Tarea"},
    "summary": "REPORTING - ...",
    "assignee": {"name": "yennyestefanny.medin@asesormasmovil.es"},
    "customfield_10100": "BST-13120",
    "components": [{"name": "IA"}, {"name": "REPORTING"}],
    "customfield_21901": {"id": "28300"},
    "description": "..."
  }
}
```

Auth: `Bearer $JIRA_PAT` (de settings.json) contra `https://jiranext.masorange.es/rest/api/2/issue`

---

## Estructura de tickets Jira

| Ticket | Descripción | Estado |
|---|---|---|
| BST-13120 | Épica raíz — CC_INFORME_SLA_FIJO | Abierta |
| BST-13121 | P1 — Mapeo campos ZZ_averias | ✅ Cerrada |
| BST-13127 | P2 — Query base SQL | ✅ Cerrada |
| BST-13129 | P3 — Cálculo 24h laborables | ✅ Cerrada |
| BST-13130 | P4 — Colas especiales (GIOR, SGI, Logística) | ✅ Cerrada |
| BST-13131 | P5 — Script Python + HTML | ✅ Cerrada |
| BST-13132 | P6 — Resumen IA | ✅ Cerrada |
| BST-13133 | P7 — Email + Task Scheduler | ✅ Cerrada |
| BST-13134 | P8 — Validación con datos reales | ✅ Cerrada |
| BST-13277 | AUDITORIA — Validación query Logística (FECHA_ULTIMA_LABEL_LOGISTICA + ILOCALIZABLE) | ✅ Cerrada |
| BST-13140 | REPORTING — FECHA_ULTIMA_LABEL_GIOR en ZZ_averias (Yenny) | ✅ Cerrada |
| BST-13215 | REPORTING — Nuevo campo FECHA_ULTIMA_ENTRADA_SAT2 en ZZ_averias (Yenny) | ✅ Entregado |
| BST-13220 | REPORTING — Nuevo campo FECHA_ACCION_PENDIENTE_CLIENTE en ZZ_averias (Yenny) | ⬜ Pendiente |
| BST-13293 | TV P2 — Query base TGJIRA-SATN2-ZL | 🔵 En progreso |
| BST-13294 | TV P3 — Logística TV | 🔵 En progreso |
| BST-13295 | TV P4 — OPITs activos | 🔵 En progreso |
| BST-13331 | REPORTING — FECHA_RELLAMADA / NUMERO_RELLAMADAS (Yenny) | ⬜ Pendiente Yenny |
| BST-13345 | Integrar TV en informe_sla_fijo.py y email diario | ⬜ Pendiente |
| BST-13346 | Mejoras UI/UX dashboard: filtros OPITs, búsqueda, gráfica agregación | 🔵 Implementado 22/06 |
| BST-13347 | REPORTING — Validar lógica ILOCALIZABLE en Logística TV (Yenny) | ⬜ Pendiente Yenny |
| BST-13142 | FASE 2 — Histórico diario en BigQuery | ⬜ Futuro |
| BST-13143 | FASE 3 — Cloud Run deployment | ⬜ Futuro (pendiente proyecto GCP) |

---

## Scope (Fase 1)

- **Tabla BQ**: mm-operaciones-bigquery.datastudio.ZZ_averias
- **Carga**: ~08:30h con datos hasta 00:00 del día anterior. FECHA_CARGA = CURRENT_DATE()
- **Cola principal**: TGJIRA-SATN2-STFIJO-ZL
- **Servicio**: TIPO_SERVICIO = 'FIBRA'
- **Tipos**: AVERIA (FTTH) + TECNICO SOLICITADO POR CLIENTE
- **Excluidos**: masivas (IDR no nulo), colectivas (COLECTIVA = 'SI'), tickets fantasma (FECHA_CREACION < 2026-01-01)
- **Volumen estimado**: ~3.300 tickets activos en scope diario

---

## Reglas de negocio clave

### Estados bajo responsabilidad SAT2
REGISTRADA · IN PROGRESS · DERIVADA · PENDIENTE CLIENTE · ESCALADA EXTERNO

### Cuándo NO es nuestra responsabilidad (excluir del informe)
- FSM_STATUS IN ('CITADA', 'PENDIENTE CITA') → contrata tiene cita activa en su sistema
- ESTADO_ESCALADO_EXTERNO IN ('EN PROGRESO', 'OPENACTIVE', 'PENDIENTE DE ACEPTACION') → proveedor externo activo

### Cuándo SÍ es nuestra responsabilidad (incluir)
- ESCALADA EXTERNO con ESTADO_ESCALADO_EXTERNO IN ('CLEARED', 'CLOSED', 'CERRADA', 'INVALIDA', 'CLOSED.CANCELED') → proveedor nos lo devolvió
- Cualquier otro estado sin proveedor activo

### Inicio del reloj de 24h
El reloj arranca desde el momento en que el ticket entra en responsabilidad de SAT2:

| Caso | Campo usado |
|---|---|
| Ticket nuevo sin devolución | FECHA_CREACION |
| Devuelto por contrata (FSM) | FECHA_ULTIMA_DEVUELTA_FSM |
| Devuelto por red franqueada (TESA) | FECHA_ULTIMA_DEVUELTA_FRANQUEADA |
| Devuelto por proveedor externo puro (Orange, ADAMO) | FECHA_ULTIMA_ACTUALIZACION ⚠️ (limitación: ver BST-13140) |
| Ambas devoluciones presentes | GREATEST(FSM, FRANQUEADA) |

### Excepción de agendamiento
Si MOTIVO_PENDIENTE_CLIENTE_TG = 'AGENDADO PRUEBAS' y APPOINMENT_DATE > hoy → no contar como incumplimiento.

### SLA
- 24 horas continuas (SAT2 trabaja 08:00-00:00, 7 días a la semana)
- Email enviado solo de lunes a viernes a las 09:00h

---

## Colas especiales (Fase 1 excluidas, Fase P4)

| Cola | Regla |
|---|---|
| TGJIRA-ESCALADO GIOR (Vodafone) | Responsabilidad por LABELS: DISPATCHING_MANUAL = nuestra / GIOR_ENCURSO = Vodafone |
| TGJIRA-SATN2-STFIJO-SGI | SLA permisivo: información real cada 48h |
| TGJIRA-LOGISTICA_ST | Tabla separada, SLA diferente, fases por labels |

---

## Limitación conocida

Para proveedores externos puros (Orange, ADAMO, TESA sin FSM), BQ no registra el timestamp exacto de cuándo devolvieron el ticket. Se usa FECHA_ULTIMA_ACTUALIZACION como aproximación. Solución pendiente: BST-13140 (extracción del grid por Yenny).

---

## Roadmap

- **Fase 1 — Fijo** (actual): ✅ Completado técnicamente. Semana 16/06: revisión diaria del informe en producción para detectar anomalías antes de ampliar destinatarios.
- **Fase 2 — TV** (próxima semana): Samuel dará contexto, grupos y etiquetas. Base SQL/Python/HTML de Fijo reutilizable — será adaptación. Logística TV tiene etiquetas distintas a Fijo.
- **Fase 3 — Email ampliado**: Ampliar destinatarios cuando Fijo + TV estén estables. Email v2 con cuerpo corto operativo (solo KPIs).
- **Fase 4 — KPI Global** (futuro): Fijo + TV unificados en un único informe con visión consolidada del servicio técnico.
- **Fase 5 — Histórico BQ** (futuro): Tabla `mm-backoffice-bigquery.SSTT.sla_fijo_diario` con registro por ticket por día → evolución temporal del KPI.

---

## Archivos del proyecto

```
INFORME_SLA_FIJO/
├── CLAUDE.md              # Este archivo
├── query_base_p2.sql      # Query SQL base (P2+P3) — funcional en BQ
├── query_sgi.sql          # Query SGI (P4) — SLA 48h, pendiente validar con datos reales
└── reportes/              # (futuro P5) HTMLs generados diariamente
```

---

## Lógica GIOR (Vodafone) — documentada en BST-13130

Cola: TGJIRA-ESCALADO GIOR. Sin integración directa → responsabilidad por LABELS:
- `CREAR_GIOR` → SAT2 responsable (hay que crear ticket en Vodafone — estado transitorio)
- `GIOR_ENCURSO` → Vodafone gestionando (excluir del informe)
- `GIOR_GESTIONADO` → Vodafone devuelve, SAT2 responsable (nuestro reloj corre)
- `DISPATCHING_MANUAL` → SAT2 controla el despacho (nuestro reloj corre)

Flujo: CREAR_GIOR → [SAT2 crea ticket] → GIOR_ENCURSO → [Vodafone gestiona] → GIOR_GESTIONADO → [SAT2 actúa]

Campo pendiente de Yenny: `FECHA_ULTIMA_LABEL_GIOR` (en BST-13140) — **imprescindible**: el reloj SAT2 arranca desde que se puso la última label GIOR relevante, no desde FECHA_REVISION_N2 ni FECHA_CREACION. Sin este campo GIOR no se puede implementar.

---

## Estado actual

*Actualizado: 2026-06-15 — Samuel Minguez*

- **P1-P8 completados** ✅
- P2: query STFIJO-ZL funcional — ~1.230 tickets diarios, ~33% INCUMPLE
- P3: horas laborables 08:00-00:00 implementadas con lógica MAX (FECHA_ULTIMA_ENTRADA_SAT2 incluida)
- P4: SGI, GIOR y Logística operativos. GIOR pendiente de FECHA_ULTIMA_LABEL_GIOR (Yenny, BST-13140)
- P5: Script Python genera fijo.html + global.html diariamente
- P7: Task Scheduler `BOST_SLA_Informe_Fijo` activo — L-V 09:00h. Email visual a samuel.minguez@masorange.es
- BST-13142 puente: histórico hasta 14 días desde HTML generados. SVG evolutivo en global.html
- BST-13143: Global Dashboard en producción con datos reales
- **P8 completado** ✅: todas las colas validadas (STFIJO-ZL, SGI, GIOR, Logística). Ver VALIDACION_P8.md
- FECHA_AGENDADO_PRUEBAS (BST-13220): entregado por Yenny y validado 15/06. Excepción AGENDADO PRUEBAS ya implementada en query_base_p2.sql (líneas 127-129). 121/122 tickets con fecha futura válida → excluidos correctamente
- ILOCALIZABLE: sin excepción (decisión de negocio). Cuenta 24h desde última gestión N2. Ya cubierto por el flujo normal de la query
- Logística: FECHA_ULTIMA_LABEL_LOGISTICA implementada en query_logistica.sql (campo entregado por Yenny el 15/06, BST-13271 cerrada). Prioridad normal: FECHA_ULTIMA_LABEL_LOGISTICA → FECHA_REVISION_N2 → FECHA_CREACION. Excepción CLIENTE ILOCALIZABLE: reloj desde FECHA_REVISION_N2 (cuando el agente puso ILOCALIZABLE), aunque sea posterior a la label. Validado con 4 tickets el 15/06
