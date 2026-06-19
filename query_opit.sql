-- =====================================================================
-- OPIT — Tickets activos con OPIT vinculado (Fijo + TV)
--        Vista de seguimiento: estado OPIT, días abierto, alerta reclamación
-- Épica: BST-13120 | Ticket: BST-13295
--
-- Fuentes de OPIT (BST-13295 — campo REMOTE_LINK_OPIT añadido por Yenny):
--   ISSUE_OPIT       → OPIT vinculado directamente en el ticket (campo nativo)
--   REMOTE_LINK_OPIT → OPIT vinculado como enlace remoto (campo Yenny)
--   Pueden coexistir ambos; se unifican con COALESCE priorizando ISSUE_OPIT
--
-- Prefijos OPIT: TTV- (TV), PROV- (Fijo), MYS- (otros), OPIT- (remoto)
-- Alertas: >5 días laborables → amarillo, >10 días → rojo
-- =====================================================================

SELECT
  z.CLAVE,
  z.TIPO_SERVICIO,
  z.MARCA,
  z.COLA_PETICIONES,
  z.ESTADO_AVERIA,
  -- Clave OPIT unificada: ISSUE_OPIT tiene preferencia, REMOTE_LINK_OPIT como fallback
  COALESCE(NULLIF(z.ISSUE_OPIT,''), NULLIF(z.REMOTE_LINK_OPIT,''))        AS opit_clave,
  COALESCE(NULLIF(z.OPIT_STATUS,''), NULLIF(z.REMOTE_LINK_OPIT_STATUS,'')) AS opit_status,
  COALESCE(NULLIF(z.OPIT_SUMMARY,''), NULLIF(z.REMOTE_LINK_OPIT_SUMMARY,'')) AS opit_summary,
  -- Indicador de origen para diagnóstico
  CASE
    WHEN z.ISSUE_OPIT IS NOT NULL AND z.ISSUE_OPIT != ''
      AND z.REMOTE_LINK_OPIT IS NOT NULL AND z.REMOTE_LINK_OPIT != '' THEN 'AMBOS'
    WHEN z.ISSUE_OPIT IS NOT NULL AND z.ISSUE_OPIT != '' THEN 'ISSUE_OPIT'
    ELSE 'REMOTE_LINK'
  END AS opit_origen,
  z.PRIO_OPIT,
  DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid')    AS fecha_creacion_opit,
  DATE(z.FECHA_ASIGNACION_OPIT, 'Europe/Madrid')  AS fecha_asignacion_opit,
  z.FECHA_RESOLUCION_OPIT,                         -- NULL = abierto
  -- Días naturales desde creación OPIT (solo cuando hay fecha, si es REMOTE_LINK puede ser NULL)
  CASE
    WHEN z.FECHA_CREACION_OPIT IS NOT NULL THEN
      DATE_DIFF(
        DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'),
        DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid'),
        DAY
      )
    ELSE NULL
  END AS dias_opit_abierto,
  -- Alerta reclamación
  CASE
    WHEN z.FECHA_CREACION_OPIT IS NULL THEN 'SIN_FECHA'
    WHEN DATE_DIFF(
      DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'),
      DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid'),
      DAY
    ) > 10 THEN 'CRITICO'
    WHEN DATE_DIFF(
      DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'),
      DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid'),
      DAY
    ) > 5  THEN 'AVISO'
    ELSE        'OK'
  END AS alerta_opit,
  DATE(z.FECHA_CREACION, 'Europe/Madrid') AS fecha_creacion_ticket
FROM `mm-operaciones-bigquery.datastudio.ZZ_averias` z
WHERE z.FECHA_CARGA = CURRENT_DATE()
  -- Incluir tickets con OPIT nativo O con enlace remoto (BST-13295)
  AND (
    (z.ISSUE_OPIT IS NOT NULL AND z.ISSUE_OPIT != '')
    OR (z.REMOTE_LINK_OPIT IS NOT NULL AND z.REMOTE_LINK_OPIT != '')
  )
  AND z.FECHA_RESOLUCION_OPIT IS NULL        -- solo OPITs abiertos
  AND z.ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
  AND (z.FECHA_CIERRE IS NULL OR z.FECHA_CIERRE > CURRENT_TIMESTAMP())
  AND z.TIPO_SERVICIO IN ('FIBRA', 'TV')
  -- Fijo: solo averías SAT2 (mismo criterio que informe principal)
  AND NOT (z.TIPO_SERVICIO = 'FIBRA' AND z.TIPO NOT IN ('AVERIA (FTTH)', 'TECNICO SOLICITADO POR CLIENTE'))
  AND z.MARCA NOT IN ('EUSKALTEL','R','RACCTEL','TELECABLE','VIRGIN TELCO')
  -- Excluir OPITs de Operaciones CB (no son responsabilidad SAT2)
  AND COALESCE(NULLIF(z.OPIT_SUMMARY,''), NULLIF(z.REMOTE_LINK_OPIT_SUMMARY,'')) NOT LIKE '[OPCBI]%'
ORDER BY
  z.TIPO_SERVICIO,
  dias_opit_abierto DESC NULLS LAST,
  z.CLAVE
