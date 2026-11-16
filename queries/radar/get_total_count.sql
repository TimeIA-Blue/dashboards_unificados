-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: count (int)
SELECT
    SUM(QT_CONTAGEM)
FROM
    BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA cd
WHERE NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'