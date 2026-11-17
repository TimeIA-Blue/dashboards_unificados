from datetime import date

import polars as pl

from client import ch_client
from queries.general import get_company_names
from relatorio.radar.helpers import (
    _load_raw_interruptions,
    build_interruptions,
    format_seconds,
)


def _load_radar_locations(client) -> pl.DataFrame:
    return pl.DataFrame(
        client.query_df(
            """
        SELECT
            CD_RADAR,
            CG_LATITUDE,
            CG_LONGITUDE
        FROM BD_ANALYTICS_SIR.V_RADAR_INFO
        """
        )
    )


def eval_interruptions(
    cnpj: str, date_range: tuple[date, date]
) -> tuple[pl.DataFrame, int, int, str, str, pl.DataFrame]:
    client = ch_client()

    company_names = get_company_names()
    interLocal = build_interruptions(
        _load_raw_interruptions(cnpj, date_range), company_names
    )
    interLocal = interLocal.join(
        _load_radar_locations(client), on="CD_RADAR", how="left"
    )

    interLocal = interLocal.with_columns(
        pl.col("DT_MES").dt.strftime("%m/%Y").alias("month")
    )
    mean_inter = interLocal["delta"].mean()
    dev_inter = interLocal["delta"].std()

    top_equips = interLocal.group_by("NO_RADAR").agg(
        pl.col("delta").mean().alias("mean_delta"), pl.count("delta").alias("count")
    )
    top_equips = top_equips.sort("count", descending=True)
    top_equips = top_equips.with_columns(
        pl.col("mean_delta").cast(int).map_elements(format_seconds).alias("mean_delta")
    )
    top_equips = top_equips.rename(
        {
            "NO_RADAR": "Nome do equipamento",
            "mean_delta": "Duração média das interrupções",
            "count": "Número de interrupções",
        }
    )

    interLocal = interLocal.drop(
        [
            "delta",
            "delta_h",
            "VL_TOLERANCIA",
            "CG_LATITUDE",
            "CG_LONGITUDE",
        ]
    )
    interLocal = interLocal.rename(
        {
            "CD_RADAR": "Código do equipamento",
            "NO_RADAR": "Nome do equipamento",
            "DT_INSTANTE_ANTERIOR": "Data/hora início da interrupção",
            "DT_INSTANTE": "Data/hora fim da interrupção",
            "month": "Mês",
            "delta_fmt": "Duração da interrupção",
        }
    )

    total_inter = len(interLocal)
    equip_count = interLocal["Código do equipamento"].n_unique()
    mean_inter = format_seconds(int(mean_inter))  # ty: ignore[invalid-argument-type]
    dev_inter = format_seconds(int(dev_inter))  # ty: ignore[invalid-argument-type]

    return interLocal, total_inter, equip_count, mean_inter, dev_inter, top_equips
