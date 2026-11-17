-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields:
--  NU_CNPJ (string), CD_PRACA (int), NO_PRACA (string),
--  DT_INSTANTE_ANTERIOR (datetime), DT_INSTANTE (datetime),
--  VL_DELTA (int), VL_TOLERANCIA (float), DT_MES (string#date)
SELECT
    NU_CNPJ,
    CD_PRACA,
    NO_PRACA,
    -- Truncar início do mês
    greatest(
        DT_INSTANTE_ANTERIOR,
        DT_INICIO_MES
    ) AS DT_INSTANTE_ANTERIOR,
    -- Truncar fim do mês
    least(
        DT_INSTANTE,
        addSeconds(addMonths(DT_INICIO_MES, 1), -1)
    ) AS DT_INSTANTE,
    dateDiff('second', DT_INSTANTE_ANTERIOR, DT_INSTANTE) AS VL_DELTA,
    VL_TOLERANCIA,
    formatDateTime(DT_INSTANTE_ANTERIOR, '%Y-%m') AS DT_MES
FROM (
    SELECT
        *,
        arrayJoin(
            arrayMap(
                x -> addMonths(DT_PRIMEIRO_MES, x),
                range(dateDiff('month', DT_PRIMEIRO_MES, toStartOfMonth(DT_INSTANTE)) + 1)
            )
        ) AS DT_INICIO_MES
    FROM (
        SELECT
            *,
            toStartOfMonth(DT_INSTANTE_ANTERIOR) AS DT_PRIMEIRO_MES
        FROM BD_ANALYTICS_SIR.MV_PEDAGIO_INTERRUPCOES
    )
)
WHERE
    NU_CNPJ = '{cnpj}' AND
    DT_INSTANTE_ANTERIOR BETWEEN '{date_start}' AND '{date_end}'
ORDER BY NU_CNPJ, CD_PRACA, DT_INSTANTE_ANTERIOR