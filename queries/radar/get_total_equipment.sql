-- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
-- OUT fields: total_equipment (int)
SELECT COUNT(DISTINCT CD_RADAR) AS total_equipment
FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
WHERE
  NU_CNPJ = '{cnpj}' AND
  DT_DIA BETWEEN '{date_start}' AND '{date_end}';