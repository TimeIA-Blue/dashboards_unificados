-- IN parameters: cnpj (string)
-- OUT fields: DT_DIA (date), QT_CONTAGEM (int)
SELECT
    cte_all_dates.DT_DIA,
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
            min(toDate(DT_INSTANTE)) AS DT_DATA_INICIO,
            max(toDate(DT_INSTANTE)) AS DT_DATA_FIM
        FROM BD_RAW_SIR_ORIGEM.TB_REGISTRO_TRAFEGO_PEDAGIO
        WHERE CD_SEQ_CONCESSIONARIA = (
            SELECT DISTINCT CD_SEQ_CONCESSIONARIA
            FROM BD_RAW_SIR_ORIGEM.TB_CONCESSIONARIA
            WHERE NU_CNPJ = '{cnpj}'
        )
    )
) AS cte_all_dates
LEFT JOIN
(
    SELECT
        DT_DIA,
        SUM(QT_CONTAGEM) AS QT_CONTAGEM
    FROM BD_ANALYTICS_SIR.MV_PEDAGIO_CONTAGEM_DIARIA
    WHERE NU_CNPJ = '{cnpj}'
    GROUP BY DT_DIA
) AS r
ON cte_all_dates.DT_DIA = r.DT_DIA
ORDER BY DT_DIA