from datetime import date

import polars as pl

from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES
from relatorio.pedagio.helpers import (
    DS_TIPO_BY_CODE,
    TIPO_EQUIPAMENTO,
    build_interruptions,
)


def _equipment_summary(violations: pl.DataFrame) -> pl.DataFrame:
    summary = violations.group_by(
        ["NU_CNPJ", "DT_MES", "VL_TEMPO_MAX_INTERRUPCAO", "DS_TIPO"]
    ).agg(pl.len().alias("size"))
    hours = summary["VL_TEMPO_MAX_INTERRUPCAO"] / 3600
    return (
        summary.with_columns(
            [
                pl.col("size").eq(0).alias("ST_CUMPRIDO"),
                # VL_VALOR_ESPERADO is a string with the format "0 (Xh)" where X is the number of hours
                pl.format("0 ({:.0f}h)", hours).alias("VL_VALOR_ESPERADO"),
            ]
        )
        .rename({"size": "VL_VALOR"})
        .drop("VL_TEMPO_MAX_INTERRUPCAO")
    )


def _equipment_violations(
    interruptions: pl.DataFrame, params: pl.DataFrame
) -> pl.DataFrame:
    equip_params = params.filter(pl.col("CD_TIPO_INTERRUPCAO") == TIPO_EQUIPAMENTO)
    if equip_params.is_empty():
        return pl.DataFrame()

    max_seconds = int(
        equip_params.select(pl.col("VL_TEMPO_MAX_INTERRUPCAO") * 3600).item()
    )

    df = interruptions.with_columns_seq(
        [
            pl.lit(max_seconds).alias("VL_TEMPO_MAX_INTERRUPCAO"),
            pl.col("VL_DELTA").gt(pl.lit(max_seconds)).alias("VIOLATION"),
            pl.lit("Equipamento").alias("DS_TIPO"),
        ]
    )
    return df


def build_param_summary(
    daily_volume: pl.DataFrame,
    params: pl.DataFrame,
    interruptions: pl.DataFrame,
) -> pl.DataFrame:
    if params.is_empty():
        return pl.DataFrame()

    table = daily_volume.group_by("DT_DIA").agg(pl.col("QT_CONTAGEM").sum())
    table = table.join(params, how="left")
    table = table.with_columns(pl.col("CD_TIPO_INTERRUPCAO").replace(DS_TIPO_BY_CODE))
    table = table.explode("DS_TIPO").drop_nulls()

    summary = _equipment_summary(_equipment_violations(interruptions, params))
    table = table.join(summary, how="left")

    no_violations_expr = (
        (pl.col("DS_TIPO") == "Sistema")
        & pl.col("ST_CUMPRIDO").is_nan()
        & (pl.col("QT_CONTAGEM") > 0)
    )
    table = table.with_columns(
        pl.when(no_violations_expr)
        .then(pl.lit(True))
        .otherwise(pl.col("ST_CUMPRIDO"))
        .alias("ST_CUMPRIDO")
    )
    table = table.with_columns(
        pl.col("ST_CUMPRIDO").replace({True: "Sim", False: "Não"}).alias("ST_CUMPRIDO")
    )
    table = table.with_columns(
        pl.when(pl.col("VL_VALOR_ESPERADO").is_nan())
        .then(pl.format("0 ({:.0f}h)", pl.col("VL_TEMPO_MAX_INTERRUPCAO") / 3600))
        .otherwise(pl.col("VL_VALOR_ESPERADO"))
        .alias("VL_VALOR_ESPERADO")
    )
    table = table.with_columns(
        pl.when(pl.col("VL_VALOR").is_nan())
        .then(pl.lit(0))
        .otherwise(pl.col("VL_VALOR"))
        .alias("VL_VALOR")
    )

    return table.drop(
        ["QT_CONTAGEM", "CD_TIPO_INTERRUPCAO", "VL_TEMPO_MAX_INTERRUPCAO"]
    )


def eval_params(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    date_start_str = date_range[0].strftime("%Y-%m-%d")
    date_end_str = date_range[1].strftime("%Y-%m-%d")

    raw_interruptions = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_interruptions"],
        {
            "cnpj": cnpj,
            "date_start": date_start_str,
            "date_end": date_end_str,
        },
        True,
    )
    daily_volume = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_daily_volume"],
        {
            "cnpj": cnpj,
            "date_start": date_start_str,
            "date_end": date_end_str,
        },
        True,
    )
    interruptions = build_interruptions(raw_interruptions)
    params = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        True,
    )
    if params.is_empty():
        return pl.DataFrame()
    param_summary = build_param_summary(daily_volume, params, interruptions)
    df_eval_f = param_summary.filter(pl.col("VL_VALOR_ESPERADO") != "-")
    # month from YYYY-MM to MM/YYYY
    df_eval_f.with_columns(
        pl.col("DT_MES").str.strptime(pl.Date, "%Y-%m").dt.strftime("%m/%Y")
    )
    df_eval_f = df_eval_f.rename(
        {
            "VL_VALOR_ESPERADO": "Valor esperado",
            "DT_MES": "Mês",
            "tipo": "Parâmetro",
            "val": "Valor observado",
            "cumpriu": "Cumprimento",
        }
    )
    return df_eval_f
