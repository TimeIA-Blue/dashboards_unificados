from pathlib import Path
from typing import Final, TypedDict


class PedagioQueries(TypedDict):
    get_company_params: Path
    """
    :param cnpj (string)
    :return : DataFrame["NU_CNPJ" (string), "CD_TIPO_INTERRUPCAO" (UInt8), "VL_TEMPO_MAX_INTERRUPCAO" (UInt16), "VL_PCT_MAX_INTERRUPCAO" (Float32), "CD_DEPLOY_ID" (UInt16), "DT_DEPLOY_TIMESTAMP" (DateTime)]
    """
    get_daily_volume: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_PRACA_PEDAGIO" (int), "DT_DIA" (string#date),
    "QT_CONTAGEM" (int)]
    """
    get_evasions: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame[
        "NU_CNPJ" (string), "CD_PRACA" (int), "NO_PRACA" (string),
        "DT_MES" (string#date), "QT_CONTAGEM" (int)
    ]
    """
    get_gaps: Path
    """
    :param cnpj (string)
    :return: DataFrame["DT_DIA" (datetime), "QT_CONTAGEM" (int)],
    """
    get_interruptions: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame[
        "NU_CNPJ" (string), "CD_PRACA" (int), "NO_PRACA" (string),
        "DT_INSTANTE_ANTERIOR" (datetime), "DT_INSTANTE" (datetime),
        "VL_DELTA" (int), "VL_TOLERANCIA" (float), "DT_MES" (string#date)
    ]    
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
    "get_company_params": Path("queries", "pedagio", "get_company_params.sql"),
    "get_daily_volume": Path("queries", "pedagio", "get_daily_volume.sql"),
    "get_evasions": Path("queries", "pedagio", "get_evasions.sql"),
    "get_gaps": Path("queries", "pedagio", "get_gaps.sql"),
    "get_interruptions": Path("queries", "pedagio", "get_interruptions.sql"),
    "get_total_tolls": Path("queries", "pedagio", "get_total_tolls.sql"),
    "get_failing_tolls": Path("queries", "pedagio", "get_failing_tolls.sql"),
    "get_toll_map": Path("queries", "pedagio", "get_toll_map.sql"),
    "get_total_count": Path("queries", "pedagio", "get_total_count.sql"),
}
