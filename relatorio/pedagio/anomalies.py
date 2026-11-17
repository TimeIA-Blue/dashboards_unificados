from datetime import date

import polars as pl

from client import ch_client
from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES
from relatorio.pedagio.helpers import _load_praca_locations


def build_evasoes(
    evasoes_all: pl.DataFrame,
    locations: pl.DataFrame,
    date_range: tuple[date, date],
) -> pl.DataFrame:
    min_month, max_month = date_range
    merged = evasoes_all.join(locations, on="CD_PRACA", how="left")
    return merged.filter(
        pl.col("DT_MES").is_between(pl.lit(min_month), pl.lit(max_month))
    )


def eval_anomalies(cnpj: str, date_range: tuple[date, date]):
    client = ch_client()
    locations = _load_praca_locations(client)
    raw_evasoes = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_evasions"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        True,
    )
    evasoesLocal = build_evasoes(raw_evasoes, locations, date_range)

    # mean of p_evasao per cd_praca
    anomMean = evasoesLocal.group_by("CD_PRACA").agg(
        pl.col("VL_PCT_EVASOES").mean().alias("mean_p_evasao")
    )
    qtd_high = anomMean.filter(pl.col("mean_p_evasao") >= 0.1).height
    qtd_medium = anomMean.filter(
        (pl.col("mean_p_evasao") >= 0.05) & (pl.col("mean_p_evasao") < 0.1)
    ).height
    qtd_low = anomMean.filter(
        (pl.col("mean_p_evasao") >= 0.01) & (pl.col("mean_p_evasao") < 0.05)
    ).height
    qtd_very_low = anomMean.filter(pl.col("mean_p_evasao") < 0.01).height
    qtds = (qtd_high, qtd_medium, qtd_low, qtd_very_low)

    total_evasions = evasoesLocal["QT_TOTAL_EVASOES"].sum()

    anomMap = evasoesLocal.group_by(
        ["CD_PRACA", "NO_PRACA", "CG_LATITUDE", "CG_LONGITUDE"]
    ).agg(pl.col("QT_TOTAL_EVASOES").mean().alias("count"))
    anomMap = anomMap.join(anomMean, on="CD_PRACA")
    anomMap = anomMap.with_columns(
        pl.when(pl.col("mean_p_evasao") >= 0.1)
        .then(pl.lit("#e63131"))
        .when(pl.col("mean_p_evasao") >= 0.05)
        .then(pl.lit("#e6b800"))
        .when(pl.col("mean_p_evasao") >= 0.01)
        .then(pl.lit("#00cc00"))
        .otherwise(pl.lit("#0066ff"))
        .alias("color")
    )

    anomPctMonth = evasoesLocal.group_by(["CD_PRACA", "NO_PRACA", "DT_MES"]).agg(
        pl.col("VL_PCT_EVASOES").mean().alias("p_evasao")
    )

    return total_evasions, qtds, anomMap, anomPctMonth
