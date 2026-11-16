-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: QT_CONTAGEM (int)
SELECT
    COUNT(*) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS
WHERE
    NU_CNPJ = '{cnpj}'
    AND DT_ACIONAMENTO_RECURSO BETWEEN '{date_start}' AND '{date_end}'