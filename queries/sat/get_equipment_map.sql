-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: CD_SAT (int), NO_SAT (string), CG_LATITUDE (float), CG_LONGITUDE(float), QT_CONTAGEM (int)
SELECT
    CD_SEQ_SAT AS CD_SAT,
    info.NO_IDENTIFICADOR AS NO_SAT,
    CG_LATITUDE,
    CG_LONGITUDE,
    COUNT(*) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA cd
LEFT JOIN
    BD_ANALYTICS_SIR.V_SAT_INFO info
ON
    cd.CD_SEQ_SAT = info.CD_SEQ_SAT
WHERE NU_CNPJ LIKE '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
GROUP BY ALL