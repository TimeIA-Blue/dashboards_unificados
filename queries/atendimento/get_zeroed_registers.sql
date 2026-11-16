-- NAME: get_zeroed_registers.sql
-- IN parameters: cnpj (string), threshold_dist (float), threshold_time (float)
-- OUT fields: DT_MES (datetime), QT_CONTAGEM (int), `QT_ZEROS` (int), `QT_AUTOACIONADOS` (int), `QT_INVALIDOS` (int)
SELECT
    DT_MES,
    COUNT(*) AS `QT_CONTAGEM`,
    countIf(Z) AS `QT_ZEROS`,
    countIf(Z_AUTOACIONADO) AS `QT_AUTOACIONADOS`,
    countIf(Z AND NOT Z_AUTOACIONADO) AS `QT_INVALIDOS`
FROM (
    SELECT
        toStartOfMonth(DT_ACIONAMENTO_RECURSO) AS DT_MES,
        geoDistance(CG_LONGITUDE_OCORRENCIA, CG_LATITUDE_OCORRENCIA, CG_LONGITUDE_ATENDIMENTO, CG_LATITUDE_ATENDIMENTO) AS DIST_M,
        (DIST_M / CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) * 0.06 AS VEL_KMH,
        toBool(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS < {threshold_time}) AS Z,
        toBool(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS < {threshold_time} AND DIST_M < {threshold_dist}) AS Z_AUTOACIONADO
    FROM BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS
    WHERE
        DS_TIPO_SERVICO IN ('Mecânico', 'Médico') AND
        DS_TIPO_VEICULO_RECURSO IN ('Ambulância C', 'Ambulância D', 'Guincho Leve', 'Guincho Pesado') AND
        NU_CNPJ = '{cnpj}' AND
        DT_ACIONAMENTO_RECURSO BETWEEN '{date_start}' AND '{date_end}'
)
GROUP BY DT_MES