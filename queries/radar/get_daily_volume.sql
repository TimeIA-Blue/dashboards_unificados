-- IN parameters: date_start (string#date), date_end (string#date)
-- OUT fields:
--  DT_DIA (string#date), QT_CONTAGEM (int)
WITH
    date_range AS (
        SELECT toDate('{date_start}') + number AS DT_DIA
        FROM system.numbers
        WHERE number <= dateDiff('day', toDate('{date_start}'), toDate('{date_end}'))
    ),
    counts AS (
        SELECT DT_DIA, SUM(QT_CONTAGEM) AS QT_CONTAGEM
        FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
        WHERE NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
        GROUP BY NU_CNPJ, DT_DIA
    )
SELECT
    d.DT_DIA,
    NULLIF(cnt.QT_CONTAGEM, 0) AS QT_CONTAGEM
FROM date_range d
LEFT JOIN counts cnt
ON d.DT_DIA = cnt.DT_DIA
ORDER BY d.DT_DIA