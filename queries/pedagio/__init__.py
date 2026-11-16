from pathlib import Path
from typing import Final, TypedDict


class PedagioQueries(TypedDict):
    get_company_params: Path
    """
    :param cnpj (string)
    :return : DataFrame["NU_CNPJ" (string), "CD_TIPO_INTERRUPCAO" (UInt8), "VL_TEMPO_MAX_INTERRUPCAO" (UInt16), "VL_PCT_MAX_INTERRUPCAO" (Float32), "CD_DEPLOY_ID" (UInt16), "DT_DEPLOY_TIMESTAMP" (DateTime)]
    """
    get_gaps: Path
    """
    :param cnpj (string)
    :return: DataFrame["DT_DIA" (datetime), "QT_CONTAGEM" (int)],
    """
    get_total_tolls: Path
    """
    :param cnpj (string)
    :return: DataFrame["QT_TOTAL_PRACAS" (int)]
    """
    get_failing_tolls: Path
    """
    :param cnpj (string)
    :return: DataFrame["CD_RADAR" (int), "NO_RADAR" (string), "QT_CONTAGEM" (int)]
    """
    get_toll_map: Path
    """
    :param cnpj (string)
    :return: DataFrame["CD_RADAR" (int), "NO_RADAR" (string), "CG_LATITUDE" (float), "CG_LONGITUDE"(float), "QT_CONTAGEM" (int)]
    """
    get_total_count: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return DataFrame["QT_CONTAGEM" (int)]
    """


AVAILABLE_PEDAGIO_QUERIES: Final[PedagioQueries] = {
    "get_company_params": Path("queries", "radar", "get_company_params.sql"),
    "get_gaps": Path("queries", "pedagio", "get_gaps.sql"),
    "get_total_tolls": Path("queries", "pedagio", "get_total_tolls.sql"),
    "get_failing_tolls": Path("queries", "pedagio", "get_failing_tolls.sql"),
    "get_toll_map": Path("queries", "pedagio", "get_toll_map.sql"),
    "get_total_count": Path("queries", "pedagio", "get_total_count.sql"),
}
