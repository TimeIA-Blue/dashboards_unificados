-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: CD_SAT (int), NO_SAT (String), DT_INSTANTE_ANTERIOR, DT_INSTANTE (DateTime), DIFF_SEC, DIFF_HOR (float), DT_MES (timestamp) CG_LATITUDE, CG_LONGITUDE Float64
SELECT
    CD_SEQ_SAT AS CD_SAT,
    info.NO_IDENTIFICADOR AS NO_SAT,
    DT_INSTANTE_ANTERIOR,
    DT_INSTANTE,
    DIFF_SEC,
    DIFF_HOR,
    toStartOfMonth(DT_INSTANTE_ANTERIOR) AS DT_MES,
    info.CG_LATITUDE AS CG_LATITUDE,
    info.CG_LONGITUDE AS CG_LONGITUDE
FROM
    BD_ANALYTICS_SIR.MV_SAT_INTERVALOS si
INNER JOIN
    BD_ANALYTICS_SIR.V_SAT_INFO info
ON
    si.CD_SEQ_SAT = info.CD_SEQ_SAT
WHERE
    NU_CNPJ = '{cnpj}'
    AND DT_INSTANTE BETWEEN '{date_start}' AND '{date_end}'
    AND DIFF_SEC > 1800;