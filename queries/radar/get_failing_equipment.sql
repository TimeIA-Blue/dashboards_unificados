-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: CD_RADAR (int), NO_RADAR (string), count (int)
SELECT
    CD_RADAR,
    r.NO_IDENTITIFICADOR AS NO_RADAR,
    SUM(QT_CONTAGEM) AS count
FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA cd
INNER JOIN BD_RAW_SIR_ORIGEM.TB_RADAR r
ON cd.CD_RADAR = r.CD_SEQ_RADAR
WHERE NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
GROUP BY ALL
HAVING count < 1000