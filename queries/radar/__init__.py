from pathlib import Path
from typing import Final, TypedDict


class RadarQueries(TypedDict):
    get_company_params: Path
    """
    :param cnpj (string)
    :return : DataFrame["cnpj" (string), "tipo_interrup" (UInt8), "tempo_max_interrup" (UInt16), "pct_max_interrup" (Float32), "deploy_id" (UInt16), "deploy_timestamp" (DateTime)]
    """
    get_equipment_map: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_RADAR" (int), "NO_RADAR" (string), "CG_LATITUDE" (float), "CG_LONGITUDE"(float), "count" (int)]
    """
    get_failing_equipment: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["CD_RADAR" (int), "NO_RADAR" (string), "count" (int)]
    """
    get_gaps: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame["date" (datetime), "count" (int)],
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


AVAILABLE_RADAR_QUERIES: Final[RadarQueries] = {
    "get_company_params": Path("queries", "radar", "get_company_params.sql"),
    "get_equipment_map": Path("queries", "radar", "get_equipment_map.sql"),
    "get_failing_equipment": Path("queries", "radar", "get_failing_equipment.sql"),
    "get_gaps": Path("queries", "radar", "get_gaps.sql"),
    "get_total_count": Path("queries", "radar", "get_total_count.sql"),
    "get_total_equipment": Path("queries", "radar", "get_total_equipment.sql"),
}
