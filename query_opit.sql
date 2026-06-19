-- =====================================================================
-- OPIT — Tickets activos con OPIT vinculado (Fijo + TV)
--        Vista de seguimiento: estado OPIT, días abierto, alerta reclamación
-- Épica: BST-13120 | Ticket: BST-13295
--
-- Los tickets con OPIT siguen computando en SLA normal.
-- Este informe es complementario: visibilidad sobre OPITs que necesitan reclamación.
--
-- Prefijos OPIT: TTV- (TV), PROV- (Fijo), MYS- (otros)
-- Alertas: >5 días laborables → amarillo, >10 días → rojo
-- =====================================================================

SELECT
  z.CLAVE,
  z.TIPO_SERVICIO,
  z.MARCA,
  z.COLA_PETICIONES,
  z.ESTADO_AVERIA,
  z.ISSUE_OPIT,
  z.OPIT_STATUS,
  z.OPIT_SUMMARY,
  z.PRIO_OPIT,
  DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid')    AS fecha_creacion_opit,
  DATE(z.FECHA_ASIGNACION_OPIT, 'Europe/Madrid')  AS fecha_asignacion_opit,
  z.FECHA_RESOLUCION_OPIT,                         -- NULL = abierto
  -- Días naturales desde creación OPIT
  DATE_DIFF(
    DATE(CURRENT_TIMESTAMP(), 'Europe/Madrid'),
    DATE(z.FECHA_CREACION_OPIT, 'Europe/Madrid'),
    DAY
  ) AS dias_opit_abierto,
  -- Alerta reclamación
  CASE
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
  AND z.ISSUE_OPIT IS NOT NULL
  AND z.ISSUE_OPIT != ''
  AND z.FECHA_RESOLUCION_OPIT IS NULL        -- solo OPITs abiertos
  AND z.ESTADO_AVERIA IN ('REGISTRADA','IN PROGRESS','DERIVADA','PENDIENTE CLIENTE','ESCALADA EXTERNO')
  AND (z.FECHA_CIERRE IS NULL OR z.FECHA_CIERRE > CURRENT_TIMESTAMP())
  AND z.TIPO_SERVICIO IN ('FIBRA', 'TV')
  -- Fijo: solo averías SAT2 (mismo criterio que informe principal)
  -- TV: todos los TIPOs son válidos (avería/configuración son nuestros)
  AND NOT (z.TIPO_SERVICIO = 'FIBRA' AND z.TIPO NOT IN ('AVERIA (FTTH)', 'TECNICO SOLICITADO POR CLIENTE'))
  AND z.MARCA NOT IN ('EUSKALTEL','R','RACCTEL','TELECABLE','VIRGIN TELCO')
  -- Excluir OPITs de Operaciones CB (no son responsabilidad SAT2)
  AND (z.OPIT_SUMMARY IS NULL OR z.OPIT_SUMMARY NOT LIKE '[OPCBI]%')
ORDER BY
  z.TIPO_SERVICIO,
  dias_opit_abierto DESC,
  z.CLAVE
