-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: CD_SAT (int), NO_SAT (string), CD_RODOVIA (int), DS_TIPO_RODOVIA (string), CG_LATITUDE (float), CG_LONGITUDE (float)
SELECT DISTINCT
    CD_SEQ_SAT,
    info.NO_IDENTIFICADOR AS NO_SAT,
    info.CD_RODOVIA AS CD_RODOVIA,
    info.DS_TIPO_RODOVIA AS DS_TIPO_RODOVIA,
    info.CG_LATITUDE AS CG_LATITUDE,
    info.CG_LONGITUDE AS CG_LONGITUDE
FROM
    BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA cd
INNER JOIN
    BD_ANALYTICS_SIR.V_SAT_INFO info
ON
    cd.CD_SEQ_SAT = info.CD_SEQ_SAT
WHERE
    NU_CNPJ = '{cnpj}' AND DT_INSTANTE BETWEEN '{date_start}' AND '{date_end}'