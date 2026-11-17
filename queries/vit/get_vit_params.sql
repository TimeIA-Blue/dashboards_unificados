-- IN parameters: cnpj (string)
-- OUT fields: VIT parameter fields for the latest deploy
SELECT *
FROM BD_PER.TB_PARAMETROS_VIT
WHERE
    cnpj = '{cnpj}'
    AND deploy_id = (
        SELECT MAX(deploy_id)
        FROM BD_PER.TB_PARAMETROS_VIT
        WHERE cnpj = '{cnpj}'
    )
