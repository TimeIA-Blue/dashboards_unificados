-- IN parameters: none
-- OUT fields: NU_CNPJ, start_date, end_date
SELECT
    NU_CNPJ,
    toDate(min(DT_INSTANTE)) AS start_date,
    toDate(max(DT_INSTANTE)) AS end_date
FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
GROUP BY NU_CNPJ
