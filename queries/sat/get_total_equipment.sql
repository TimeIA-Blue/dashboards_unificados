-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: QT_TOTAL_EQUIPAMENTO (int)
SELECT
    COUNT(*) AS QT_TOTAL_EQUIPAMENTO
FROM (
    SELECT DISTINCT
        CD_SEQ_SAT
    FROM
        BD_RAW_SIR_ORIGEM.TB_REGISTRO_TRAFEGO_SAT
    WHERE
        CD_SEQ_CONCESSIONARIA = (SELECT DISTINCT CD_SEQ_CONCESSIONARIA FROM BD_RAW_SIR_ORIGEM.TB_CONCESSIONARIA WHERE NU_CNPJ = '{cnpj}') AND
        DT_INSTANTE BETWEEN '{date_start}' AND '{date_end}'
)