-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields:
--  NU_CNPJ (string), CD_RADAR (int), NO_RADAR (string),
--  DT_INSTANTE_ANTERIOR (datetime), DT_INSTANTE (datetime),
--  delta (int), VL_TOLERANCIA (float), DT_MES (string#date)
SELECT
    CD_RADAR,
    NO_RADAR,
    -- Truncar início do mês
    greatest(DT_INSTANTE_ANTERIOR, month_start) AS DT_INSTANTE_ANTERIOR,
    -- Truncar fim do mês
    least(DT_INSTANTE, addSeconds(addMonths(month_start, 1), -1)) AS DT_INSTANTE,
    dateDiff(
        'second',
        DT_INSTANTE_ANTERIOR,
        DT_INSTANTE
    ) AS delta,
    VL_TOLERANCIA,
    toStartOfMonth(DT_INSTANTE_ANTERIOR) AS DT_MES
FROM (
    SELECT
        *,
        arrayJoin(
            arrayMap(
                x -> addMonths(start_month, x),
                range(dateDiff('month', start_month, toStartOfMonth(DT_INSTANTE)) + 1)
            )
        ) AS month_start
    FROM (
        SELECT
            *,
            toStartOfMonth(DT_INSTANTE_ANTERIOR) AS start_month
        FROM BD_ANALYTICS_SIR.MV_RADAR_INTERRUPCOES
        WHERE NU_CNPJ = '{cnpj}'
    )
)
WHERE
    greatest(DT_INSTANTE_ANTERIOR, month_start) < least(
        DT_INSTANTE,
        addSeconds(addMonths(month_start, 1), -1)
    )
    AND DT_INSTANTE_ANTERIOR < addDays(toDate('{date_end}'), 1)
    AND DT_INSTANTE >= toDate('{date_start}')
ORDER BY CD_RADAR, DT_INSTANTE_ANTERIOR
