-- NAME: get_company_time_range.sql
-- IN parameters: cnpj (string)
-- OUT fields: DT_DATA_INICIO (datetime), DT_DATA_FIM (datetime)
SELECT
    min(toDate(DT_ACIONAMENTO_RECURSO)) AS DT_DATA_INICIO,
    max(toDate(DT_ACIONAMENTO_RECURSO)) AS DT_DATA_FIM
FROM BD_RAW_SIR.TB_ATENDIMENTO
WHERE NU_CNPJ = '{cnpj}'