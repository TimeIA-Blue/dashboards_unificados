from datetime import date

import polars as pl

from queries import get_query_result
from queries.radar import AVAILABLE_RADAR_QUERIES


def _all_anomalies(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    AnomAll = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_anomalies"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        True,
    )
    AnomAll = AnomAll.filter(
        pl.col("VL_VELOCIDADE_MEDIA")
        .lt(20)
        .or_(pl.col("VL_VELOCIDADE_MAXIMA").gt(200))
        .or_(pl.col("VL_VELOCIDADE_MINIMA").lt(20))
    ).with_columns(pl.col("VL_VELOCIDADE_MEDIA").lt(20).alias("med_anom"))
    return AnomAll


def build_anomalies(
    anomalies_all: pl.DataFrame, date_range: tuple[date, date]
) -> pl.DataFrame:
    min_month, max_month = date_range
    return anomalies_all.filter(
        pl.col("DT_MES").is_between(pl.lit(min_month), pl.lit(max_month))
    )


def eval_anomalies(cnpj: str, date_range: tuple[date, date]):
    anomLocal = build_anomalies(_all_anomalies(cnpj, date_range), date_range)

    count_anom = len(anomLocal)
    count_equip = anomLocal["CD_RADAR"].n_unique()
    count_mean_anom = anomLocal.filter(pl.col("med_anom"))["CD_RADAR"].n_unique()

    anom_fmt = anomLocal.drop(
        [
            "CD_RADAR",
            "QT_CONTAGEM",
            "CG_LATITUDE",
            "CG_LONGITUDE",
        ]
    )
    anom_fmt = anom_fmt.sort("DT_MES")
    anom_fmt = anom_fmt.filter(pl.col("med_anom")).drop("med_anom")
    anom_fmt = anom_fmt.with_columns(
        pl.col("VL_VELOCIDADE_MEDIA").round(2).alias("vel_med")
    )
    anom_fmt = anom_fmt.with_columns(
        [
            pl.format("{} km/h", pl.col("vel_med")).alias("vel_med"),
            pl.format("{} km/h", pl.col("VL_VELOCIDADE_MINIMA")).alias("vel_min"),
            pl.format("{} km/h", pl.col("VL_VELOCIDADE_MAXIMA")).alias("vel_max"),
        ]
    )
    anom_fmt = anom_fmt.rename(
        {
            "DT_MES": "Mês",
            "vel_med": "Velocidade média",
            "vel_min": "Velocidade mínima",
            "vel_max": "Velocidade máxima",
            "NO_RADAR": "Radar",
        }
    ).drop(
        [
            "VL_VELOCIDADE_MEDIA",
            "VL_VELOCIDADE_MINIMA",
            "VL_VELOCIDADE_MAXIMA",
            "QT_CONTAGEM_ACIMA_LIMITE",
        ]
    )
    # put Mês as first column
    anom_fmt = anom_fmt.select(
        ["Mês"] + [col for col in anom_fmt.columns if col != "Mês"]
    )

    anomForMap = anomLocal[
        [
            "CD_RADAR",
            "NO_RADAR",
            "CG_LATITUDE",
            "CG_LONGITUDE",
            "QT_CONTAGEM",
            "med_anom",
        ]
    ].unique()

    # if medAnom is True, color red, else yellow
    anomForMap = anomForMap.with_columns(
        pl.when(pl.col("med_anom"))
        .then(pl.list([255, 0, 0, 0.5]))
        .otherwise(pl.list([255, 255, 0, 0.5]))
        .alias("color")
    )
    return anomForMap, anom_fmt, count_anom, count_equip, count_mean_anom
