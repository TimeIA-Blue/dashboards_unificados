-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: QT_CONTAGEM (int)
SELECT
    COUNT(*) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
WHERE
    DT_INSTANTE BETWEEN '{date_start}' AND '{date_end}' AND
    NU_CNPJ = '{cnpj}'