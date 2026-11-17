-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: NU_CNPJ, DT_DIA, QT_CONTAGEM
WITH
    toDate('{date_start}') AS DT_DATA_INICIO,
    toDate('{date_end}') AS DT_DATA_FIM,
    date_range AS (
        SELECT DT_DATA_INICIO + number AS DT_DIA
        FROM system.numbers
        WHERE number <= dateDiff('day', DT_DATA_INICIO, DT_DATA_FIM)
    ),
    companies AS (
        SELECT DISTINCT NU_CNPJ
        FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
        WHERE NU_CNPJ = '{cnpj}'
    ),
    counts AS (
        SELECT
            NU_CNPJ,
            toDate(DT_INSTANTE) AS DT_DIA,
            COUNT(DISTINCT DS_PLACA) AS QT_CONTAGEM
        FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
        WHERE
            DT_INSTANTE BETWEEN DT_DATA_INICIO AND DT_DATA_FIM
            AND NU_CNPJ = '{cnpj}'
        GROUP BY NU_CNPJ, DT_DIA
    )
SELECT
    c.NU_CNPJ AS NU_CNPJ,
    d.DT_DIA AS DT_DIA,
    NULLIF(QT_CONTAGEM, 0) AS QT_CONTAGEM
FROM companies c
CROSS JOIN date_range d
LEFT JOIN counts t
    ON c.NU_CNPJ = t.NU_CNPJ AND d.DT_DIA = t.DT_DIA
ORDER BY c.NU_CNPJ, d.DT_DIA
