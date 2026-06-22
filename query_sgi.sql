-- =====================================================================
-- P4 — SGI: Tickets activos TGJIRA-SATN2-STFIJO-SGI
--      SLA permisivo: 48h laborables desde última gestión N2 (o creación)
--      SAT2 trabaja 08:00-00:00, 7 días/semana (misma fórmula que P3)
-- Épica: BST-13120 CC_INFORME_SLA_FIJO | Ticket: BST-13130
-- =====================================================================

WITH tickets_sgi AS (
  SELECT
    CLAVE,
    TIPO,
    ESTADO_AVERIA,
    COLA_PETICIONES,
    LABELS,
    MOTIVO_PENDIENTE_CLIENTE_TG,
    FECHA_AGENDADO_PRUEBAS,
    FECHA_CREACION,
    FECHA_ULTIMA_ACTUALIZACION,
    FECHA_REVISION_N2,
    MOTIVO_SOLICITUD,
    TIPO_SERVICIO,
    FECHA_RELLAMADA,
    NUMERO_RELLAMADAS
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND COLA_PETICIONES = 'TGJIRA-SATN2-STFIJO-SGI'
    AND TIPO_SERVICIO = 'FIBRA'
    AND TIPO IN ('AVERIA (FTTH)', 'TECNICO SOLICITADO POR CLIENTE')
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
),

calcular_inicio_medicion AS (
  -- En SGI el reloj corre desde la última gestión N2 confirmada.
  -- Si no hay gestión N2, arranca desde la creación del ticket.
  -- No aplica lógica FSM/FRANQ/EXTERNO (SGI no escala a contratas/externos).
  SELECT
    *,
    CASE
      WHEN FECHA_REVISION_N2 IS NOT NULL THEN FECHA_REVISION_N2
      ELSE FECHA_CREACION
    END AS inicio_medicion,
    CASE
      WHEN FECHA_REVISION_N2 IS NOT NULL THEN 'GESTION_N2'
      ELSE 'FECHA_CREACION'
    END AS origen_reloj
  FROM tickets_sgi
),

calcular_horas_laborables AS (
  -- Misma fórmula que P3 (08:00-00:00, 7 días/semana, zona Europe/Madrid)
  -- Umbral de incumplimiento: 48h laborables (no 24h)
  SELECT
    *,
    ROUND(
      (
        (UNIX_DATE(DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'))
         - UNIX_DATE(DATE(inicio_medicion, 'Europe/Madrid'))) * 16 * 3600
        + GREATEST(0, TIME_DIFF(TIME(CURRENT_TIMESTAMP(), 'Europe/Madrid'), TIME '08:00:00', SECOND))
        - GREATEST(0, TIME_DIFF(TIME(inicio_medicion, 'Europe/Madrid'), TIME '08:00:00', SECOND))
      ) / 3600.0,
      1
    ) AS horas_laborables
  FROM calcular_inicio_medicion
),

detectar_incumplimiento AS (
  SELECT
    *,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), inicio_medicion, HOUR) AS horas_calendario,
    CASE
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'AGENDADO PRUEBAS'
        AND FECHA_AGENDADO_PRUEBAS > CURRENT_TIMESTAMP()
      THEN 'EXCEPTO_AGENDAMIENTO'
      WHEN horas_laborables > 48
      THEN 'INCUMPLE'
      ELSE 'CUMPLE'
    END AS estado_sla
  FROM calcular_horas_laborables
)

SELECT
  CLAVE,
  TIPO,
  ESTADO_AVERIA,
  COLA_PETICIONES,
  MOTIVO_SOLICITUD,
  TIPO_SERVICIO,
  FECHA_CREACION,
  DATE(inicio_medicion)  AS fecha_ultima_gestion,
  origen_reloj,
  horas_calendario,
  horas_laborables       AS horas_sin_gestion,
  estado_sla,
  CASE estado_sla
    WHEN 'INCUMPLE'             THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin gestión (SLA 48h SGI)')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    ELSE                             '✅ Dentro de SLA (48h SGI)'
  END AS estado_display,
  FECHA_RELLAMADA,
  NUMERO_RELLAMADAS
FROM detectar_incumplimiento
ORDER BY horas_laborables DESC, CLAVE
