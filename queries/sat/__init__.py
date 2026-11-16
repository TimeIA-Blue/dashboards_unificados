from pathlib import Path
from typing import Final, TypedDict


class SatQueries(TypedDict):
    get_company_params: Path
    """
    :param cnpj (string)
    :return : DataFrame["cnpj" (string), "tipo_interrup" (UInt8), "tempo_max_interrup" (UInt16), "pct_max_interrup" (Float32)]
    """
    get_date_range: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return DataFrame["INSTANTE_INICIO" (datetime), "INSTANTE_FIM" (datetime)]
    """
    get_equipment_info: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return : DataFrame["CD_SAT" (int), "NO_SAT" (string), "CD_RODOVIA" (int), "DS_TIPO_RODOVIA" (string), "CG_LATITUDE" (float), "CG_LONGITUDE" (float)]
    """
    get_equipment_map: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_SAT" (int), "NO_SAT" (string), "CG_LATITUDE" (float), "CG_LONGITUDE"(float), "count" (int)]
    """
    get_failing_equipment: Path
    """
    :param cnpj (string), threshold (int), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_SAT" (int), "NO_SAT" (string), "count" (int)]
    """
    get_formulaic_downtimes: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_SAT" (int), "DIFF_HOR" (float), "DT_MES" (datetime)]
    """
    get_gaps: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["date" (datetime), "count" (int)]
    """
    get_total_count: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    -- IN parameters: cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["count" (int)]
    """
    get_total_equipment: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["total_equipment" (int)]
    """


AVAILABLE_SAT_QUERIES: Final[SatQueries] = {
    "get_company_params": Path("queries", "sat", "get_company_params.sql"),
    "get_date_range": Path("queries", "sat", "get_date_range.sql"),
    "get_equipment_info": Path("queries", "sat", "get_equipment_info.sql"),
    "get_equipment_map": Path("queries", "sat", "get_equipment_map.sql"),
    "get_failing_equipment": Path("queries", "sat", "get_failing_equipment.sql"),
    "get_formulaic_downtimes": Path("queries", "sat", "get_formulaic_downtimes.sql"),
    "get_gaps": Path("queries", "sat", "get_gaps.sql"),
    "get_total_count": Path("queries", "sat", "get_total_count.sql"),
    "get_total_equipment": Path("queries", "sat", "get_total_equipment.sql"),
}

SAT_GET_AVAILABLE_COMPANIES = "SELECT DISTINCT NU_CNPJ FROM passagem_sat"
