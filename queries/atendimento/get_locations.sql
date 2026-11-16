-- IN parameters: cnpj (string), resolution (int), date_start (string#date), date_end (string#date)
-- OUT fields: CD_H3 (string), QT_CONTAGEM (int)
SELECT
    hex(
        geoToH3(
            CG_LONGITUDE_ATENDIMENTO,
            CG_LATITUDE_ATENDIMENTO,
            {resolution}
        )
    ) AS CD_H3,
    COUNT(*) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS
WHERE
    NU_CNPJ = '{cnpj}'
    AND DT_ACIONAMENTO_RECURSO BETWEEN '{date_start}'
    AND '{date_end}'
GROUP BY
    CD_H3