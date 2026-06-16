-- =====================================================================
-- P2+P3: Query base — Tickets activos STFIJO con lógica de responsabilidad
--        y cálculo de horas laborables (08:00-00:00, 7 días/semana)
-- Épica: BST-13120 CC_INFORME_SLA_FIJO
-- Autor: Claude (Samuel Minguez)
-- =====================================================================

WITH tickets_scope AS (
  -- Aplicar filtros base: FIBRA, AVERIA+TAP, STFIJO-ZL, sin masivas/colectivas
  SELECT
    CLAVE,
    TIPO,
    ESTADO_AVERIA,
    COLA_PETICIONES,
    FSM_STATUS,
    ESTADO_ESCALADO_EXTERNO,
    NOMBRE_EXTERNO,
    LABELS,
    MOTIVO_PENDIENTE_CLIENTE_TG,
    FECHA_AGENDADO_PRUEBAS,
    FECHA_CREACION,
    FECHA_ULTIMA_DEVUELTA_FSM,
    FECHA_ULTIMA_DEVUELTA_FRANQUEADA,
    FECHA_ULTIMA_ACTUALIZACION,
    FECHA_REVISION_N2,
    FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR,
    TOTAL_DEVOLUCIONES_EXTERNO_AD_OR,
    FECHA_ULTIMA_LABEL_GIOR,
    FECHA_ULTIMA_ENTRADA_SAT2,
    MOTIVO_SOLICITUD,
    TIPO_SERVICIO
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND COLA_PETICIONES = 'TGJIRA-SATN2-STFIJO-ZL'
    AND TIPO_SERVICIO = 'FIBRA'
    AND TIPO IN ('AVERIA (FTTH)', 'TECNICO SOLICITADO POR CLIENTE')
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
),

aplicar_responsabilidad AS (
  -- Filtrar tickets que NO son nuestra responsabilidad
  -- NOTA: se usa IS NULL OR NOT IN en vez de NOT (... IN ...) porque
  --       NULL IN (lista) = NULL → NOT NULL = NULL → fila excluida incorrectamente
  SELECT * FROM tickets_scope
  WHERE
    (FSM_STATUS IS NULL OR FSM_STATUS NOT IN ('CITADA','PENDIENTE CITA'))
    AND (ESTADO_ESCALADO_EXTERNO IS NULL OR ESTADO_ESCALADO_EXTERNO NOT IN ('EN PROGRESO','OPENACTIVE','PENDIENTE DE ACEPTACION'))
),

calcular_inicio_reloj AS (
  -- Determinar desde qué momento corre el reloj de responsabilidad SAT2
  SELECT
    *,
    -- FECHA_ULTIMA_ENTRADA_SAT2 es la fuente de verdad: cuándo entró el ticket
    -- por última vez en esta cola. Puede ser más reciente que una devolución FSM/FRANQ
    -- si el ticket pasó por otras colas entremedias (p.ej. SGI → SAT2 de nuevo).
    -- Por eso tomamos el MÁXIMO entre todas las fechas relevantes y FECHA_ULTIMA_ENTRADA_SAT2.
    (SELECT MAX(f) FROM UNNEST([
      FECHA_ULTIMA_DEVUELTA_FSM,
      FECHA_ULTIMA_DEVUELTA_FRANQUEADA,
      FECHA_ULTIMA_LABEL_GIOR,
      FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR,
      FECHA_ULTIMA_ENTRADA_SAT2,
      FECHA_CREACION  -- fallback garantizado (nunca NULL)
    ]) AS f WHERE f IS NOT NULL)
    AS inicio_reloj_24h
  FROM aplicar_responsabilidad
),

ajustar_por_gestion_n2 AS (
  -- Si el agente N2 actuó después del inicio del reloj, el punto de medición
  -- avanza a esa actuación. El informe detecta así tickets sin gestión reciente,
  -- no solo tickets sin gestión desde la devolución.
  -- FECHA_REVISION_N2 es la evidencia de gestión activa del agente N2.
  SELECT
    *,
    CASE
      WHEN FECHA_REVISION_N2 IS NOT NULL AND FECHA_REVISION_N2 > inicio_reloj_24h
        THEN FECHA_REVISION_N2
      ELSE inicio_reloj_24h
    END AS inicio_medicion,
    -- Indica qué campo determinó el inicio del reloj (el que ganó el MAX)
    CASE
      WHEN FECHA_REVISION_N2 IS NOT NULL AND FECHA_REVISION_N2 > inicio_reloj_24h
        THEN 'GESTION_N2'
      WHEN inicio_reloj_24h = FECHA_ULTIMA_ENTRADA_SAT2
        THEN 'ENTRADA_SAT2'
      WHEN inicio_reloj_24h = FECHA_ULTIMA_DEVUELTA_FSM
        OR inicio_reloj_24h = FECHA_ULTIMA_DEVUELTA_FRANQUEADA
        OR inicio_reloj_24h = FECHA_ULTIMA_LABEL_GIOR
        THEN 'FSM/FRANQ/GIOR'
      WHEN inicio_reloj_24h = FECHA_ULTIMA_DEVUELTA_EXTERNO_AD_OR
        THEN 'EXTERNO_AD_OR'
      ELSE 'FECHA_CREACION'
    END AS origen_reloj
  FROM calcular_inicio_reloj
),

calcular_horas_laborables AS (
  -- P3: Cálculo de horas laborables SAT2 (08:00-00:00, 7 días/semana)
  -- Mide desde inicio_medicion (última gestión N2 o inicio de responsabilidad)
  --
  -- Fórmula: bh(T1, T2) = (dias_diff × 16h) + bh_dia(T2) - bh_dia(T1)
  -- donde bh_dia(T) = MAX(0, TIME(T, tz) - 08:00) en segundos
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
  FROM ajustar_por_gestion_n2
),

detectar_incumplimiento AS (
  SELECT
    *,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), inicio_medicion, HOUR) AS horas_calendario,
    CASE
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'AGENDADO PRUEBAS'
        AND FECHA_AGENDADO_PRUEBAS > CURRENT_TIMESTAMP()
      THEN 'EXCEPTO_AGENDAMIENTO'
      WHEN horas_laborables > 24
      THEN 'INCUMPLE'
      ELSE 'CUMPLE'
    END AS estado_sla
  FROM calcular_horas_laborables
)

-- OUTPUT FINAL
SELECT
  CLAVE,
  TIPO,
  ESTADO_AVERIA,
  FSM_STATUS,
  ESTADO_ESCALADO_EXTERNO,
  NOMBRE_EXTERNO,
  MOTIVO_PENDIENTE_CLIENTE_TG,
  MOTIVO_SOLICITUD,
  TIPO_SERVICIO,
  FECHA_CREACION,
  DATE(inicio_reloj_24h)  AS fecha_inicio_responsabilidad,
  DATE(inicio_medicion)   AS fecha_ultima_gestion,
  origen_reloj,
  horas_calendario,
  horas_laborables        AS horas_sin_gestion,
  estado_sla,
  CASE estado_sla
    WHEN 'INCUMPLE'            THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin gestión')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    ELSE                            '✅ Dentro de SLA'
  END AS estado_display
FROM detectar_incumplimiento
ORDER BY horas_laborables DESC, CLAVE
