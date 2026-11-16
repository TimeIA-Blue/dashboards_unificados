-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: QT_CONTAGEM (int)
SELECT
    SUM(QT_CONTAGEM) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.MV_PEDAGIO_CONTAGEM_DIARIA
WHERE
    NU_CNPJ = '{cnpj}'
    AND DT_DIA BETWEEN '{date_start}'
    AND '{date_end}'