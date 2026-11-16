-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: DT_DIA (date), QT_CONTAGEM (int)
SELECT
    all_dates.DT_DIA AS DT_DIA,
    ifNull(r.QT_CONTAGEM, 0) AS QT_CONTAGEM
FROM
(
    SELECT
        arrayJoin(
            range(
                toUInt32(toDate(DT_DATA_INICIO)),
                toUInt32(toDate(DT_DATA_FIM)) + 1
            )
        ) AS d,
        toDate(d) AS DT_DIA
    FROM
    (
        SELECT
            min(DT_DIA) AS DT_DATA_INICIO,
            max(DT_DIA) AS DT_DATA_FIM
        FROM BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA
        WHERE NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
    )
) AS all_dates
LEFT JOIN
(
    SELECT
        DT_DIA,
        SUM(QT_CONTAGEM) AS QT_CONTAGEM
    FROM BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA
    WHERE NU_CNPJ = '{cnpj}'
    GROUP BY DT_DIA
) AS r
ON all_dates.DT_DIA = r.DT_DIA
ORDER BY DT_DIA