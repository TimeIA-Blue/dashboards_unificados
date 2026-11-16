-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: CD_RADAR (int), NO_RADAR (string), CG_LATITUDE (float), CG_LONGITUDE(float), count (int)
SELECT
    CD_RADAR,
    info.NO_RADAR AS NO_RADAR,
    info.CG_LATITUDE AS CG_LATITUDE,
    info.CG_LONGITUDE AS CG_LONGITUDE,
    COUNT(*) AS COUNT
FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA cd
INNER JOIN BD_ANALYTICS_SIR.V_RADAR_INFO info
ON cd.CD_RADAR = info.CD_RADAR
WHERE NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
GROUP BY ALL