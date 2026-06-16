-- =====================================================================
-- P4 — GIOR: Tickets activos TGJIRA-ESCALADO GIOR con label CREAR_GIOR
--
-- Scope: SAT2 debe crear ticket en Vodafone (estado transitorio).
--        Flujo: CREAR_GIOR → [SAT2 crea] → GIOR_ENCURSO (Vodafone) → GIOR_GESTIONADO (vuelve a STFIJO-ZL)
--
-- NOTA: GIOR_GESTIONADO y DISPATCHING_MANUAL no aparecen en esta cola.
--       Al ponerse esas labels, el ticket vuelve automáticamente a STFIJO-ZL
--       y queda cubierto por query_base_p2.sql con FECHA_ULTIMA_LABEL_GIOR.
--
--       FECHA_ULTIMA_LABEL_GIOR no aplica aquí (solo cubre GIOR_GESTIONADO/DISPATCHING_MANUAL).
--       Para CREAR_GIOR se usa FECHA_REVISION_N2 si existe, sino FECHA_CREACION.
--
-- SLA: pendiente confirmar con negocio — provisional 24h
-- Épica: BST-13120 CC_INFORME_SLA_FIJO | Ticket: BST-13130
-- =====================================================================

WITH tickets_gior AS (
  SELECT
    CLAVE,
    TIPO,
    ESTADO_AVERIA,
    COLA_PETICIONES,
    LABELS,
    MOTIVO_PENDIENTE_CLIENTE_TG,
    FECHA_AGENDADO_PRUEBAS,
    FECHA_CREACION,
    FECHA_REVISION_N2,
    MOTIVO_SOLICITUD,
    TIPO_SERVICIO
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND COLA_PETICIONES = 'TGJIRA-ESCALADO GIOR'
    AND LABELS LIKE '%CREAR_GIOR%'
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
),

calcular_inicio_medicion AS (
  -- CREAR_GIOR: SAT2 responsable desde la última gestión N2 o desde creación.
  -- No aplicamos FECHA_ULTIMA_LABEL_GIOR (solo cubre GIOR_GESTIONADO/DISPATCHING_MANUAL).
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
  FROM tickets_gior
),

calcular_horas_laborables AS (
  -- Misma fórmula (08:00-00:00, 7 días/semana, zona Europe/Madrid)
  -- SLA provisional: 24h (pendiente confirmar con negocio)
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
    WHEN 'INCUMPLE'             THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin crear ticket Vodafone (SLA 24h GIOR)')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    ELSE                             '✅ Dentro de SLA (24h GIOR)'
  END AS estado_display
FROM detectar_incumplimiento
ORDER BY horas_laborables DESC, CLAVE
