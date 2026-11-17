from pathlib import Path
from typing import Final, TypedDict


class RadarQueries(TypedDict):
    get_anomalies: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame[
        "CD_RADAR" (int), "DT_MES" (string#date), "CG_LATITUDE" (float),
        "CG_LONGITUDE" (float), "NO_RADAR" (string),
        "VL_VELOCIDADE_MEDIA" (float), "VL_VELOCIDADE_MINIMA" (float),
        "VL_VELOCIDADE_MAXIMA" (float), "QT_CONTAGEM_ACIMA_LIMITE" (int),
        "QT_CONTAGEM" (int)
    ]
    """
    get_company_params: Path
    """
    :param cnpj (string)
    :return : DataFrame["cnpj" (string), "tipo_interrup" (UInt8), "tempo_max_interrup" (UInt16), "pct_max_interrup" (Float32), "deploy_id" (UInt16), "deploy_timestamp" (DateTime)]
    """
    get_count_by_date: Path
    """
    :param date_start (string#date), date_end (string#date)
    :return: DataFrame["cnpj" (string), "dt" (date), "count" (int)]
    """
    get_daily_volume: Path
    """
    :param date_start (string#date), date_end (string#date)
    :return: DataFrame["DT_DIA" (date), "QT_CONTAGEM" (int)]
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
    get_interruptions: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :return: DataFrame[
        "CD_RADAR" (int), "NO_RADAR" (string),
        "DT_INSTANTE_ANTERIOR" (datetime), "DT_INSTANTE" (datetime),
        "delta" (int), "VL_TOLERANCIA" (float), "DT_MES" (string#date)
    ]
    """


AVAILABLE_RADAR_QUERIES: Final[RadarQueries] = {
    "get_anomalies": Path("queries", "radar", "get_anomalies.sql"),
    "get_company_params": Path("queries", "radar", "get_company_params.sql"),
    "get_count_by_date": Path("queries", "radar", "get_count_by_date.sql"),
    "get_daily_volume": Path("queries", "radar", "get_daily_volume.sql"),
    "get_equipment_map": Path("queries", "radar", "get_equipment_map.sql"),
    "get_failing_equipment": Path("queries", "radar", "get_failing_equipment.sql"),
    "get_gaps": Path("queries", "radar", "get_gaps.sql"),
    "get_total_count": Path("queries", "radar", "get_total_count.sql"),
    "get_total_equipment": Path("queries", "radar", "get_total_equipment.sql"),
    "get_interruptions": Path("queries", "radar", "get_interruptions.sql"),
}
