-- NAME: get_first_calls.sql
-- IN parameters: cnpj (string), threshold_dist (float), threshold_time (float), date_start (string#date), date_end (string#date)
-- OUT fields: TMI, check the SQL file

-- Prepara consulta dos primeiros acionamentos de cada tipo de recurso para cada atendimento
WITH first_ats AS (
    SELECT
        CD_GUID,
        CD_RODOVIA,
        DS_TIPO_RODOVIA,
        NU_KM_METROS,
        DS_TIPO_SERVICO,
        DS_TIPO_VEICULO_RECURSO,
        DT_CHEGADA_LOCAL,
        DT_ACIONAMENTO_RECURSO,
        CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS,
        geoDistance(
            CG_LONGITUDE_OCORRENCIA,
            CG_LATITUDE_OCORRENCIA,
            CG_LONGITUDE_ATENDIMENTO,
            CG_LATITUDE_ATENDIMENTO
        ) AS DIST_M,
        (DIST_M / CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) * 0.06 AS VEL_KMH,
        toBool(
            CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS < {threshold_time}
        ) AS Z,
        toBool(
            CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS < {threshold_time}
            AND DIST_M < {threshold_dist}
        ) AS Z_JUSTIFICADO
    FROM
        (
            SELECT
                ac.*,
                ac.CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS,
                row_number() OVER (
                    PARTITION BY CD_GUID,
                    DS_TIPO_SERVICO,
                    DS_TIPO_VEICULO_RECURSO
                    ORDER BY
                        DT_ACIONAMENTO_RECURSO
                ) AS row_number
            FROM
                BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS ac
            WHERE
                DS_TIPO_SERVICO IN ('Mecânico', 'Médico')
                AND DS_TIPO_VEICULO_RECURSO IN (
                    'Ambulância C',
                    'Ambulância D',
                    'Guincho Leve',
                    'Guincho Pesado'
                )
                AND NU_CNPJ = '{cnpj}'
                AND DT_ACIONAMENTO_RECURSO BETWEEN '{date_start}' AND '{date_end}'
                AND NOT Z
        )
    WHERE
        row_number = 1
)
-- Seleciona todas as informações de cada primeiro acionamento
-- Adiciona informações de mês e nome do trecho
SELECT
    first_ats.*,
    toStartOfMonth(DT_ACIONAMENTO_RECURSO) AS DT_MES,
    CASE WHEN t.DS_NOME_TRECHO IS NOT NULL THEN t.DS_NOME_TRECHO ELSE toString(first_ats.CD_RODOVIA) END AS key_trecho,
    t.DS_NOME_TRECHO
FROM
    first_ats
    LEFT JOIN BD_PER.TB_PARAMETROS_ATENDIMENTO t ON first_ats.CD_RODOVIA = t.CD_RODOVIA
    AND first_ats.NU_KM_METROS BETWEEN t.VL_KM_INICIAL
    AND t.VL_KM_FINAL