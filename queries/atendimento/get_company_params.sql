-- IN parameters: cnpj (string)
-- OUT fields:
--      rodovia (int), km_inicial (float), km_final (float), tipo_recurso (string),
--      tipo_parametro (int), valor (int), tipo_servico (string), nome_trecho (string)
SELECT
  * EXCEPT (
    NU_CNPJ,
    CD_DEPLOY_ID,
    DT_DEPLOY_TIMESTAMP
  )
FROM
    BD_PER.TB_PARAMETROS_ATENDIMENTO
WHERE 
    NU_CNPJ = '{cnpj}' AND
    CD_DEPLOY_ID = (
        SELECT
            MAX(CD_DEPLOY_ID)
        FROM
            BD_PER.TB_PARAMETROS_ATENDIMENTO
        WHERE
            NU_CNPJ = '{cnpj}'
    )