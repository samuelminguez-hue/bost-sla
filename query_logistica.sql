-- =====================================================================
-- P4 — LOGÍSTICA: Tickets activos TGJIRA-LOGISTICA_ST (FIBRA)
--      SLA 24h laborables desde que el equipo requiere gestión SAT2
--      Solo computa cuando hay acción requerida (no en tránsito)
--      SAT2 trabaja 08:00-00:00, 7 días/semana (misma fórmula P3)
-- Épica: BST-13120 CC_INFORME_SLA_FIJO | Ticket: BST-13130
--
-- Flujo de labels:
--   INICIO (no computa):   #CAMBIO_CPE / #CABLEDEALIMENTACION / #CAMBIO_FAST5670
--   EN TRÁNSITO (no comp): #PEDIDO_EN_VUELO
--   SAT2 RESPONSABLE 24h:  #EQUIPO_ENTREGADO / #INCIDENCIA_TRANSPORTE / #DEVUELTO_ALMACEN
--
-- Nota: la cola es compartida TV+FIJO → filtramos TIPO_SERVICIO='FIBRA'
-- Nota: FECHA_ULTIMA_LABEL_LOGISTICA es el inicio preferente del reloj (consulta 2, ZZ_averias)
-- =====================================================================

WITH tickets_logistica AS (
  SELECT
    CLAVE,
    TIPO,
    ESTADO_AVERIA,
    COLA_PETICIONES,
    LABELS,
    TIPO_SERVICIO,
    MOTIVO_SOLICITUD,
    MOTIVO_PENDIENTE_CLIENTE_TG,
    FECHA_AGENDADO_PRUEBAS,
    FECHA_CREACION,
    FECHA_ULTIMA_ACTUALIZACION,
    FECHA_REVISION_N2,
    FECHA_ULTIMA_LABEL_LOGISTICA
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND COLA_PETICIONES = 'TGJIRA-LOGISTICA_ST'
    AND TIPO_SERVICIO = 'FIBRA'
    AND TIPO IN ('AVERIA (FTTH)', 'TECNICO SOLICITADO POR CLIENTE')
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
),

clasificar_estado_flujo AS (
  -- Determina en qué fase del flujo está el ticket y si SAT2 es responsable.
  -- Labels acumulativas: tomamos la más avanzada del flujo.
  SELECT
    *,
    CASE
      WHEN LABELS LIKE '%#EQUIPO_ENTREGADO%'      THEN 'EQUIPO_ENTREGADO'
      WHEN LABELS LIKE '%#DEVUELTO_ALMACEN%'      THEN 'DEVUELTO_ALMACEN'
      WHEN LABELS LIKE '%#INCIDENCIA_TRANSPORTE%' THEN 'INCIDENCIA_TRANSPORTE'
      WHEN LABELS LIKE '%#PEDIDO_EN_VUELO%'       THEN 'PEDIDO_EN_VUELO'
      ELSE                                             'SOLO_INICIO'
    END AS estado_logistica,
    CASE
      WHEN LABELS LIKE '%#EQUIPO_ENTREGADO%'      THEN TRUE
      WHEN LABELS LIKE '%#DEVUELTO_ALMACEN%'      THEN TRUE
      WHEN LABELS LIKE '%#INCIDENCIA_TRANSPORTE%' THEN TRUE
      ELSE                                             FALSE
    END AS sat2_responsable
  FROM tickets_logistica
),

calcular_inicio_reloj AS (
  -- Solo para tickets donde SAT2 es responsable.
  -- CLIENTE ILOCALIZABLE: el reloj arranca desde FECHA_REVISION_N2 (cuando el agente
  -- detectó que no localizaba al cliente), aunque sea posterior a la label.
  -- Resto: FECHA_ULTIMA_LABEL_LOGISTICA → FECHA_REVISION_N2 → FECHA_CREACION
  SELECT
    *,
    CASE
      WHEN NOT sat2_responsable                                                                  THEN NULL
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE' AND FECHA_REVISION_N2 IS NOT NULL THEN FECHA_REVISION_N2
      WHEN FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL                                              THEN FECHA_ULTIMA_LABEL_LOGISTICA
      WHEN FECHA_REVISION_N2 IS NOT NULL                                                         THEN FECHA_REVISION_N2
      ELSE FECHA_CREACION
    END AS inicio_reloj,
    CASE
      WHEN NOT sat2_responsable                                                                  THEN 'NO_APLICA'
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE' AND FECHA_REVISION_N2 IS NOT NULL THEN 'FECHA_REVISION_N2_ILOC'
      WHEN FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL                                              THEN 'FECHA_ULTIMA_LABEL_LOGISTICA'
      WHEN FECHA_REVISION_N2 IS NOT NULL                                                         THEN 'FECHA_REVISION_N2'
      ELSE                                                                                            'FECHA_CREACION'
    END AS origen_reloj
  FROM clasificar_estado_flujo
),

calcular_horas_laborables AS (
  -- 08:00-00:00, 7 días/semana, zona Europe/Madrid (misma fórmula P3/SGI)
  -- Solo calcula para tickets donde SAT2 es responsable
  SELECT
    *,
    CASE
      WHEN NOT sat2_responsable OR inicio_reloj IS NULL THEN NULL
      ELSE ROUND(
        (
          (UNIX_DATE(DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'))
           - UNIX_DATE(DATE(inicio_reloj, 'Europe/Madrid'))) * 16 * 3600
          + GREATEST(0, TIME_DIFF(TIME(CURRENT_TIMESTAMP(), 'Europe/Madrid'), TIME '08:00:00', SECOND))
          - GREATEST(0, TIME_DIFF(TIME(inicio_reloj, 'Europe/Madrid'), TIME '08:00:00', SECOND))
        ) / 3600.0,
        1
      )
    END AS horas_laborables
  FROM calcular_inicio_reloj
),

detectar_incumplimiento AS (
  SELECT
    *,
    CASE
      WHEN NOT sat2_responsable
        THEN 'EXCLUIDO'
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'AGENDADO PRUEBAS'
        AND FECHA_AGENDADO_PRUEBAS > CURRENT_TIMESTAMP()
        THEN 'EXCEPTO_AGENDAMIENTO'
      WHEN horas_laborables > 24
        THEN 'INCUMPLE'
      ELSE 'CUMPLE'
    END AS estado_sla
  FROM calcular_horas_laborables
)

SELECT
  CLAVE,
  TIPO,
  ESTADO_AVERIA,
  TIPO_SERVICIO,
  MOTIVO_SOLICITUD,
  -- Labels relevantes para contexto
  REGEXP_EXTRACT_ALL(LABELS, r'#[A-Z_0-9]+') AS labels_array,
  estado_logistica,
  sat2_responsable,
  FECHA_CREACION,
  DATE(inicio_reloj)           AS fecha_inicio_reloj,
  origen_reloj,
  horas_laborables             AS horas_sin_gestion,
  estado_sla,
  CASE estado_sla
    WHEN 'INCUMPLE'             THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin gestión (SLA 24h)')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    WHEN 'EXCLUIDO'             THEN CONCAT('🔄 En tránsito — ', estado_logistica)
    ELSE                             '✅ Dentro de SLA (24h)'
  END AS estado_display
FROM detectar_incumplimiento
ORDER BY
  sat2_responsable DESC,   -- primero los que computan
  horas_laborables DESC,   -- peor primero
  CLAVE
