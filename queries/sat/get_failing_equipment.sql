-- IN parameters: cnpj (string), threshold (int), date_start (string#date), date_end (string#date)
-- OUT fields: CD_SAT (int), NO_SAT (string), count (int)
SELECT
    CD_SEQ_SAT,
    s.NO_IDENTITIFICADOR AS NO_SAT,
    ifNull(SUM(QT_CONTAGEM), 0) AS QT_CONTAGEM
FROM
    BD_ANALYTICS_SIR.MV_SAT_CONTAGEM_DIA cd
RIGHT JOIN
    BD_RAW_SIR_ORIGEM.TB_SAT s
ON
    cd.CD_SEQ_SAT = s.CD_SEQ_SAT
WHERE
    NU_CNPJ = '{cnpj}' AND DT_DIA BETWEEN '{date_start}' AND '{date_end}'
GROUP BY
    CD_SEQ_SAT, NO_SAT
HAVING
    QT_CONTAGEM < {threshold}