-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields:
--  CD_PRACA_PEDAGIO (int), DT_DIA (string#date), QT_CONTAGEM (int)
WITH
    date_range AS (
        SELECT toDate('{date_start}') + number AS DT_DIA
        FROM system.numbers
        WHERE number <= dateDiff('day', toDate('{date_start}'), toDate('{date_end}'))
    ),
    companies AS (
        SELECT DISTINCT CD_PRACA_PEDAGIO
        FROM BD_ANALYTICS_SIR.V_PEDAGIO_INFO
        WHERE NU_CNPJ = '{cnpj}'
    ),
    counts AS (
        SELECT CD_PRACA_PEDAGIO, DT_DIA, QT_CONTAGEM
        FROM BD_ANALYTICS_SIR.MV_PEDAGIO_CONTAGEM_DIARIA
        WHERE
            NU_CNPJ = '{cnpj}' AND
            DT_DIA BETWEEN '{date_start}' AND '{date_end}'
    )
SELECT
    c.CD_PRACA_PEDAGIO AS CD_PRACA_PEDAGIO,
    d.DT_DIA AS DT_DIA,
    NULLIF(QT_CONTAGEM, 0) AS QT_CONTAGEM
FROM companies c
CROSS JOIN date_range d
LEFT JOIN counts t
ON
    c.CD_PRACA_PEDAGIO = t.CD_PRACA_PEDAGIO AND
    d.DT_DIA = t.DT_DIA
ORDER BY c.CD_PRACA_PEDAGIO, d.DT_DIA