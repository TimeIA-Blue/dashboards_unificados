-- IN parameters: date_start (string#date), date_end (string#date)
-- OUT fields: cnpj (string), dt (date), count (int)
WITH
  toDate('{date_start}') AS start_date,
  toDate('{date_end}') AS end_date,
  date_range AS (
    SELECT start_date + number AS dt
    FROM system.numbers
    WHERE number <= dateDiff('day', start_date, end_date)
  ),
  companies AS (
    SELECT DISTINCT NU_CNPJ
    FROM BD_RAW_SIR.TB_RADAR
  ),
  counts AS (
    SELECT NU_CNPJ, toDate(DT_INSTANTE) AS dt, COUNT(*) AS cnt
    FROM BD_RAW_SIR.TB_RADAR
    WHERE DT_INSTANTE BETWEEN start_date AND end_date
    GROUP BY NU_CNPJ, dt
  )

SELECT
  c.cnpj AS cnpj,
  d.dt AS dt,
  NULLIF(cnt, 0) AS count
FROM companies c
CROSS JOIN date_range d
LEFT JOIN counts t
  ON c.cnpj = t.cnpj AND d.dt = t.dt
ORDER BY c.cnpj, d.dt