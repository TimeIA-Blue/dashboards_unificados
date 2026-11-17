-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: point identity, coordinates, and QT_CONTAGEM
SELECT
    NO_PONTO,
    DS_TIPO_PONTO,
    CG_LATITUDE,
    CG_LONGITUDE,
    COUNT(*) AS QT_CONTAGEM
FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
WHERE
    NU_CNPJ = '{cnpj}'
    AND DT_INSTANTE BETWEEN toDate('{date_start}') AND toDate('{date_end}')
GROUP BY ALL
ORDER BY QT_CONTAGEM DESC
