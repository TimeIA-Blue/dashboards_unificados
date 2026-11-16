-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: date (date), count (int)
SELECT
    all_dates.date AS date,
    ifNull(r.count, 0) AS count
FROM
(
    SELECT
        arrayJoin(
            range(
                toUInt32(toDate(min_date)),
                toUInt32(toDate(max_date)) + 1
            )
        ) AS d,
        toDate(d) AS date
    FROM
    (
        SELECT
            min(DT_DIA) AS min_date,
            max(DT_DIA) AS max_date
        FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
        WHERE
            NU_CNPJ = '{cnpj}' AND
            DT_DIA BETWEEN '{date_start}' AND '{date_end}'
    )
) AS all_dates
LEFT JOIN
(
    SELECT
        DT_DIA AS date,
        SUM(QT_CONTAGEM) AS count
    FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
    WHERE
        NU_CNPJ = '{cnpj}'
    GROUP BY date
) AS r
ON all_dates.date = r.date
ORDER BY date