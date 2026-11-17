-- IN parameters: date_start (string#date), date_end (string#date)
-- OUT fields: interruption and vehicle delay fields
SELECT
    NU_CNPJ,
    DS_TIPO_PONTO,
    CD_PONTO,
    NO_PONTO,
    CD_SENTIDO,
    NO_SENTIDO,
    DT_PASSAGEM_ANTERIOR AS DT_INSTANTE_ANTERIOR,
    DT_PASSAGEM AS DT_INSTANTE,
    DS_PLACA_ANTERIOR,
    DS_PLACA,
    (60 * VL_INTERVALO)::Int64 AS VL_DELTA
FROM BD_ANALYTICS_SIR.MV_VIT_ATRASOS
WHERE DT_PASSAGEM BETWEEN toDate('{date_start}') AND toDate('{date_end}')
