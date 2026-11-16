-- Obtém estatísticas de uma determinada região, marcada por vários hexágonos
-- Parâmetros:
-- {resolution}
-- {cnpj}
-- {tipo_servico}
-- {tipo_recurso}
-- {hexagon_list_str} (lista de hexágonos em formato hexagonal)
WITH prev AS (
  SELECT
    CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS,
    (hex(geoToH3(CG_LATITUDE_ATENDIMENTO, CG_LONGITUDE_ATENDIMENTO, {resolution})) IN {hexagon_list_str}) AS In_Regiao
  FROM
    BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS
  WHERE
    NU_CNPJ = '{cnpj}' AND
    DS_TIPO_SERVICO = '{tipo_servico}' AND
    DS_TIPO_VEICULO_RECURSO = '{tipo_recurso}' AND
    CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS > 1
)
SELECT
  avgIf(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS, In_Regiao) AS Media_Regiao,
  avg(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) AS Media_Total,
  minIf(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS, In_Regiao) AS Min_Regiao,
  min(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) AS Min_Total,
  maxIf(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS, In_Regiao) AS Max_Regiao,
  max(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) AS Max_Total,
  stddevPopStableIf(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS, In_Regiao) AS DesvioPadrao_Regiao,
  stddevPopStable(CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS) AS DesvioPadrao_Total
FROM
  prev