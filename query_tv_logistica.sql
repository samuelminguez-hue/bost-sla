-- =====================================================================
-- TV P3 — LOGÍSTICA TV: Tickets activos TGJIRA-LOGISTICA_ST (TV)
--         SLA 24h laborables desde que el equipo requiere gestión SAT2
--         SAT2 trabaja 08:00-00:00, 7 días/semana
-- Épica: BST-13120 | Ticket: BST-13294
--
-- Flujo de labels TV — casi idéntico a Fijo, solo cambian las labels de inicio:
--   INICIO (no computa):   #PENDIENTE_SWAP (envío STB) / #SWAP_SOLO_MANDO (envío mando)
--                          Equivalen a #CAMBIO_CPE / #CABLEDEALIMENTACION / #CAMBIO_FAST5670 de Fijo
--   SAT2 RESPONSABLE 24h:  #EQUIPO_ENTREGADO / #INCIDENCIA_TRANSPORTE / #DEVUELTO_ALMACEN
--                          Idéntico a Fijo
--   Sin label conocida:    Avería normal en cola logística — SLA 24h desde creación/N2
--                          (tickets en LOGISTICA_ST que no tienen gestión iniciada)
--
-- Labels informativas (no afectan SLA):
--   Agente:        TV_NOMBRE (ej: TV_LORE, TV_ALEX...)
--   Comunicación:  #WHATSAPP / #WHATSAPP_ENTREGADO
--   Contacto:      #ILOCALIZABLE_1T / #WHATSAPP_ILOC2
--
-- CASOS ESPECIALES:
--   #SMS_SWAP_ENTREGADO → se trata como #EQUIPO_ENTREGADO (automatismo que a veces
--                          no pone la etiqueta final; nota de negocio BST-13294)
--   Sin label conocida   → avería normal, SAT2 responsable 24h desde creación/N2
--
-- Marcas excluidas: EUSKALTEL / R / RACCTEL / TELECABLE / VIRGIN TELCO
-- Cola compartida TV+FIJO → filtrar TIPO_SERVICIO='TV'
-- =====================================================================

WITH tickets_logistica AS (
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
    FECHA_INICIO_ILOCALIZABLE,
    FECHA_ULTIMA_LABEL_LOGISTICA,
    FECHA_RELLAMADA,
    NUMERO_RELLAMADAS
  FROM `mm-operaciones-bigquery.datastudio.ZZ_averias`
  WHERE FECHA_CARGA = CURRENT_DATE()
    AND COLA_PETICIONES = 'TGJIRA-LOGISTICA_ST'
    AND TIPO_SERVICIO = 'TV'
    AND ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
    AND (FECHA_CIERRE IS NULL OR FECHA_CIERRE > CURRENT_TIMESTAMP())
    AND (IDR IS NULL OR IDR = '')
    AND (COLECTIVA IS NULL OR COLECTIVA = '')
    AND FECHA_CREACION >= '2026-01-01'
    AND MARCA NOT IN ('EUSKALTEL','R','RACCTEL','TELECABLE','VIRGIN TELCO')
),

clasificar_estado_flujo AS (
  SELECT
    *,
    CASE
      -- SAT2 responsable: equipo en destino o con incidencia
      WHEN LABELS LIKE '%#EQUIPO_ENTREGADO%'      THEN 'EQUIPO_ENTREGADO'
      -- #SMS_SWAP_ENTREGADO computa igual que #EQUIPO_ENTREGADO
      -- (el automatismo a veces falla en poner la etiqueta definitiva)
      WHEN LABELS LIKE '%#SMS_SWAP_ENTREGADO%'    THEN 'EQUIPO_ENTREGADO'
      WHEN LABELS LIKE '%#DEVUELTO_ALMACEN%'      THEN 'DEVUELTO_ALMACEN'
      WHEN LABELS LIKE '%#INCIDENCIA_TRANSPORTE%' THEN 'INCIDENCIA_TRANSPORTE'
      -- Inicio del proceso: SAT2 aún no es responsable
      WHEN LABELS LIKE '%#PENDIENTE_SWAP%'        THEN 'PENDIENTE_SWAP'
      WHEN LABELS LIKE '%#SWAP_SOLO_MANDO%'       THEN 'SWAP_SOLO_MANDO'
      -- Sin label conocida: avería normal en cola logística
      ELSE                                             'SIN_LABEL_LOGISTICA'
    END AS estado_logistica,
    CASE
      WHEN LABELS LIKE '%#EQUIPO_ENTREGADO%'      THEN TRUE
      WHEN LABELS LIKE '%#SMS_SWAP_ENTREGADO%'    THEN TRUE
      WHEN LABELS LIKE '%#DEVUELTO_ALMACEN%'      THEN TRUE
      WHEN LABELS LIKE '%#INCIDENCIA_TRANSPORTE%' THEN TRUE
      -- Sin label: SAT2 responsable como avería normal (24h)
      WHEN LABELS NOT LIKE '%#PENDIENTE_SWAP%'
        AND LABELS NOT LIKE '%#SWAP_SOLO_MANDO%'  THEN TRUE
      ELSE                                             FALSE
    END AS sat2_responsable
  FROM tickets_logistica
),

calcular_inicio_reloj AS (
  SELECT
    *,
    CASE
      WHEN NOT sat2_responsable THEN NULL
      -- ILOCALIZABLE con etiqueta logística posterior: la label manda sobre el ilocalizable
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE'
        AND FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL
        AND FECHA_ULTIMA_LABEL_LOGISTICA > COALESCE(FECHA_INICIO_ILOCALIZABLE, FECHA_REVISION_N2)
        THEN FECHA_ULTIMA_LABEL_LOGISTICA
      -- ILOCALIZABLE sin label logística posterior: usar FII (más preciso que N2) o N2 como fallback
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE'
        THEN COALESCE(FECHA_INICIO_ILOCALIZABLE, FECHA_REVISION_N2, FECHA_CREACION)
      -- SIN_LABEL_LOGISTICA (no ilocalizable): usar N2 o creación
      WHEN estado_logistica = 'SIN_LABEL_LOGISTICA' THEN
        COALESCE(FECHA_REVISION_N2, FECHA_CREACION)
      -- INCIDENCIA_TRANSPORTE / DEVUELTO_ALMACEN: reloj desde último intento de contacto (FII) o N2
      WHEN estado_logistica IN ('INCIDENCIA_TRANSPORTE', 'DEVUELTO_ALMACEN')
        THEN COALESCE(FECHA_INICIO_ILOCALIZABLE, FECHA_REVISION_N2, FECHA_CREACION)
      -- Caso normal (EQUIPO_ENTREGADO y resto): prioridad FECHA_ULTIMA_LABEL_LOGISTICA → N2 → CREACION
      WHEN FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL THEN FECHA_ULTIMA_LABEL_LOGISTICA
      WHEN FECHA_REVISION_N2 IS NOT NULL            THEN FECHA_REVISION_N2
      ELSE FECHA_CREACION
    END AS inicio_reloj,
    CASE
      WHEN NOT sat2_responsable THEN 'NO_APLICA'
      -- ILOCALIZABLE con label logística posterior
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE'
        AND FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL
        AND FECHA_ULTIMA_LABEL_LOGISTICA > COALESCE(FECHA_INICIO_ILOCALIZABLE, FECHA_REVISION_N2)
        THEN 'FECHA_ULTIMA_LABEL_LOGISTICA'
      -- ILOCALIZABLE sin label posterior
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE'
        AND FECHA_INICIO_ILOCALIZABLE IS NOT NULL   THEN 'FECHA_INICIO_ILOCALIZABLE'
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'CLIENTE ILOCALIZABLE'
        AND FECHA_REVISION_N2 IS NOT NULL            THEN 'FECHA_REVISION_N2_ILOC'
      WHEN estado_logistica = 'SIN_LABEL_LOGISTICA' AND FECHA_REVISION_N2 IS NOT NULL THEN 'FECHA_REVISION_N2'
      WHEN estado_logistica = 'SIN_LABEL_LOGISTICA' THEN 'FECHA_CREACION'
      WHEN estado_logistica IN ('INCIDENCIA_TRANSPORTE', 'DEVUELTO_ALMACEN') AND FECHA_INICIO_ILOCALIZABLE IS NOT NULL THEN 'FECHA_INICIO_ILOCALIZABLE_TRANSPORTE'
      WHEN estado_logistica IN ('INCIDENCIA_TRANSPORTE', 'DEVUELTO_ALMACEN') AND FECHA_REVISION_N2 IS NOT NULL         THEN 'FECHA_REVISION_N2_TRANSPORTE'
      WHEN estado_logistica IN ('INCIDENCIA_TRANSPORTE', 'DEVUELTO_ALMACEN')                                           THEN 'FECHA_CREACION'
      WHEN FECHA_ULTIMA_LABEL_LOGISTICA IS NOT NULL THEN 'FECHA_ULTIMA_LABEL_LOGISTICA'
      WHEN FECHA_REVISION_N2 IS NOT NULL            THEN 'FECHA_REVISION_N2'
      ELSE                                               'FECHA_CREACION'
    END AS origen_reloj
  FROM clasificar_estado_flujo
),

calcular_horas_laborables AS (
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
      WHEN NOT sat2_responsable                           THEN 'EXCLUIDO'
      WHEN MOTIVO_PENDIENTE_CLIENTE_TG = 'AGENDADO PRUEBAS'
        AND FECHA_AGENDADO_PRUEBAS > CURRENT_TIMESTAMP() THEN 'EXCEPTO_AGENDAMIENTO'
      WHEN horas_laborables > 24                         THEN 'INCUMPLE'
      ELSE                                                    'CUMPLE'
    END AS estado_sla
  FROM calcular_horas_laborables
)

SELECT
  CLAVE,
  TIPO,
  ESTADO_AVERIA,
  MARCA,
  TIPO_SERVICIO,
  REGEXP_EXTRACT_ALL(LABELS, r'#[A-Z_0-9]+') AS labels_array,
  estado_logistica,
  sat2_responsable,
  FECHA_CREACION,
  DATE(inicio_reloj)        AS fecha_inicio_reloj,
  origen_reloj,
  horas_laborables          AS horas_sin_gestion,
  estado_sla,
  CASE estado_sla
    WHEN 'INCUMPLE'             THEN CONCAT('⛔ ', CAST(horas_laborables AS STRING), 'h lab. sin gestión (SLA 24h)')
    WHEN 'EXCEPTO_AGENDAMIENTO' THEN '⏰ Agendado (excepción válida)'
    WHEN 'EXCLUIDO'             THEN CONCAT('🔄 En espera — ', estado_logistica)
    ELSE                             '✅ Dentro de SLA (24h)'
  END AS estado_display,
  FECHA_RELLAMADA,
  NUMERO_RELLAMADAS
FROM detectar_incumplimiento
ORDER BY
  sat2_responsable DESC,
  horas_laborables DESC,
  CLAVE
