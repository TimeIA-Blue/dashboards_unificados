-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: INSTANTE_INICIO (Timestamp), INSTANTE_FIM (Timestamp)
SELECT
    greatest(MIN(DT_DIA), toDate('{date_start}')) AS INSTANTE_INICIO,
    least(MAX(DT_DIA), toDate('{date_end}')) AS INSTANTE_FIM
FROM
    BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA
WHERE
    NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'