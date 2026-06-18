-- =====================================================================
-- TV P2 — SATN2-ZL: Tickets activos TV sin gestión (Servicio TV)
--         SLA 24h laborables desde que el ticket es responsabilidad SAT2
--         SAT2 trabaja 08:00-00:00, 7 días/semana
-- Épica: BST-13120 | Ticket: BST-13293
--
-- Colas excluidas (escalados — cuentan cuando vuelven a SATN2-ZL):
--   TGJIRA-BACKOFFICE-NTT / TGJIRA-BACKOFFICE-JZZ
--   TGJIRA-AGILE_TV_S1    / TGJIRA-ORANGE_TV_S1
--   TGJIRA-OPIT (pendiente análisis — BST-13295)
--
-- Marcas excluidas (no MasOrange, de momento fuera):
--   EUSKALTEL / R / RACCTEL / TELECABLE / VIRGIN TELCO
--
-- Logística TV: cola separada — ver query_tv_logistica.sql (BST-13294)
-- OPIT: pendiente análisis conjunto Fijo+TV (BST-13295)
-- =====================================================================

WITH tickets_scope AS (
  SELECT
    CLAVE,
    TIPO,
    ESTADO_AVERIA,
    COLA_PETICIONES,
    MARCA,
    LABELS,
    TIPO_SERVICIO,
    MOTIVO_SOLICITUD,
    MOTIVO_PENDIENTE_CLIENTE_TG,
    FECHA_AGENDADO_PRUEBAS,
    FECHA_CREACION,
    FECHA_ULTIMA_ACTUALIZACION,
    FECHA_REVISION_N2,
    FECHA_ULTIMA_ENTRADA_SAT2,
    FECHA_ULTIMA_DEVUELTA_FSM,
    FECHA_ULTIMA_DEVUELTA_FRANQUEADA,
    FSM_STATUS,
    ESTADO_ESCALADO_EXTERNO
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND TIPO_SERVICIO = 'TV'
    AND COLA_PETICIONES = 'TGJIRA-SATN2-ZL'
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
    -- Excluir marcas no MasOrange (BST-13292)
    AND MARCA NOT IN ('EUSKALTEL','R','RACCTEL','TELECABLE','VIRGIN TELCO')
    -- SOLICITUD CONFIGURACIÓN son tickets de front office que no deben computar (BST-13293)
    -- En Fijo están todos cerrados; en TV aparecen abiertos por error — mismo criterio de exclusión
    AND TIPO != 'SOLICITUD CONFIGURACIÓN'
),

-- TODO BST-13293: revisar si FSM_STATUS tiene lógica de exclusión en TV
-- (en Fijo: CITADA/PENDIENTE CITA → contrata activa → excluir)
-- En TV FSM_STATUS está relleno en casi todos los tickets — verificar valores
detectar_responsabilidad AS (
  SELECT
    *,
    CASE
      -- Contrata activa con cita → no es nuestra responsabilidad (mismo criterio que Fijo)
      WHEN FSM_STATUS IN ('CITADA','PENDIENTE CITA') THEN FALSE
      -- Proveedor externo activo
      WHEN ESTADO_ESCALADO_EXTERNO IN ('EN PROGRESO','OPENACTIVE','PENDIENTE DE ACEPTACION') THEN FALSE
      ELSE TRUE
    END AS sat2_responsable
  FROM tickets_scope
),

calcular_inicio_reloj AS (
  SELECT
    *,
    -- Inicio del reloj: campo más reciente disponible
    -- TV: FECHA_ULTIMA_ENTRADA_SAT2 casi siempre NULL (no derivan mucho)
    -- FSM: pocas devoluciones en TV — FECHA_CREACION será el origen mayoritario
    -- TODO BST-13293: validar con ATC-8534234 y otros casos reales
    CASE
      WHEN NOT sat2_responsable THEN NULL
      WHEN FECHA_ULTIMA_ENTRADA_SAT2 IS NOT NULL
        AND FECHA_ULTIMA_DEVUELTA_FSM IS NOT NULL
        THEN GREATEST(FECHA_ULTIMA_ENTRADA_SAT2, FECHA_ULTIMA_DEVUELTA_FSM)
      WHEN FECHA_ULTIMA_ENTRADA_SAT2 IS NOT NULL THEN FECHA_ULTIMA_ENTRADA_SAT2
      WHEN FECHA_ULTIMA_DEVUELTA_FSM IS NOT NULL THEN FECHA_ULTIMA_DEVUELTA_FSM
      ELSE FECHA_CREACION
    END AS inicio_reloj,
    CASE
      WHEN NOT sat2_responsable THEN 'NO_APLICA'
      WHEN FECHA_ULTIMA_ENTRADA_SAT2 IS NOT NULL
        AND FECHA_ULTIMA_DEVUELTA_FSM IS NOT NULL THEN 'MAX(ENTRADA_SAT2,FSM)'
      WHEN FECHA_ULTIMA_ENTRADA_SAT2 IS NOT NULL THEN 'FECHA_ULTIMA_ENTRADA_SAT2'
      WHEN FECHA_ULTIMA_DEVUELTA_FSM IS NOT NULL THEN 'FECHA_ULTIMA_DEVUELTA_FSM'
      ELSE 'FECHA_CREACION'
    END AS origen_reloj
  FROM detectar_responsabilidad
),

calcular_horas_laborables AS (
  -- 08:00-00:00, 7 días/semana, zona Europe/Madrid (misma fórmula que Fijo)
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
  MARCA,
  TIPO_SERVICIO,
  MOTIVO_SOLICITUD,
  FSM_STATUS,
  origen_reloj,
  DATE(inicio_reloj)       AS fecha_inicio_reloj,
  horas_laborables         AS horas_sin_gestion,
  estado_sla,
  CASE estado_sla
    WHEN 'INCUMPLE'             THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin gestión (SLA 24h)')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    WHEN 'EXCLUIDO'             THEN CONCAT('🔄 Excluido — ', FSM_STATUS)
    ELSE                             '✅ Dentro de SLA (24h)'
  END AS estado_display,
  FECHA_CREACION,
  FECHA_REVISION_N2        AS fecha_ultima_gestion
FROM detectar_incumplimiento
ORDER BY
  sat2_responsable DESC,
  horas_laborables DESC,
  CLAVE
