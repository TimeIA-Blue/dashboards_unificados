from datetime import date

import polars as pl

from queries import get_query_result
from queries.radar import AVAILABLE_RADAR_QUERIES


def format_seconds(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return "".join(parts)


DS_TIPO_BY_CODE = {
    1: ["Sistema"],
    2: ["Equipamento"],
    3: ["Sistema", "Equipamento"],
    4: ["Sistema", "Sistema (%)"],
    5: ["Sistema", "Sistema (%)", "Equipamento"],
}
TIPOS_EQUIPAMENTO = (2, 3, 5)
TIPOS_SISTEMA = (1, 3, 4, 5)
TIPOS_SISTEMA_PCT = (4, 5)

RADAR_KEYS = ["CD_RADAR", "NO_RADAR", "DT_MES"]


def _load_raw_interruptions(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_RADAR_QUERIES["get_interruptions"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


def build_interruptions(
    raw: pl.DataFrame, company_names: dict[str, str]
) -> pl.DataFrame:
    return raw.with_columns(
        [
            pl.col("delta").truediv(60 * 60).alias("delta_h"),
            pl.col("delta").map_elements(format_seconds).alias("delta_fmt"),
        ]
    )
