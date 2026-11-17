from datetime import date

import polars as pl

from queries import get_query_result
from queries.general import get_company_names
from queries.radar import AVAILABLE_RADAR_QUERIES
from relatorio.radar.helpers import (
    DS_TIPO_BY_CODE,
    RADAR_KEYS,
    TIPOS_EQUIPAMENTO,
    TIPOS_SISTEMA,
    TIPOS_SISTEMA_PCT,
    _load_raw_interruptions,
    build_interruptions,
    format_seconds,
)


def _monthly_volume(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.with_columns(pl.col("DT_DIA").dt.truncate("1mo").alias("DT_MES"))
        .group_by("DT_MES")
        .agg(pl.col("QT_CONTAGEM").sum().alias("QT_CONTAGEM"))
    )


def _monthly_availability(interruptions: pl.DataFrame) -> pl.DataFrame:
    """Mean over radars of (1 - interrupted time / seconds in month), per CNPJ/month."""
    per_radar = interruptions.group_by(RADAR_KEYS).agg(
        pl.col("delta").sum().alias("sum_delta")
    )
    seconds_in_month = per_radar["DT_MES"].dt.days_in_month() * 24 * 60 * 60
    per_radar["p"] = 1 - (per_radar["sum_delta"] / seconds_in_month)
    return (
        per_radar.group_by(["NU_CNPJ", "DT_MES"])
        .agg(pl.col("p").mean().alias("mean_p"))
        .sort(by="DT_MES")
    )


def _param_by_cnpj(
    params: pl.DataFrame, tipos: tuple[int, ...], column: str
) -> pl.DataFrame:
    """Series {NU_CNPJ: value} for concessionaires whose type is in `tipos`."""
    selected = params.filter(pl.col("CD_TIPO_INTERRUPCAO").is_in(tipos))
    return selected.drop_nulls(subset=["NU_CNPJ"]).select(["NU_CNPJ", column])


def _equipment_violations(
    interruptions: pl.DataFrame, params: pl.DataFrame
) -> pl.DataFrame:
    max_hours = _param_by_cnpj(params, TIPOS_EQUIPAMENTO, "VL_TEMPO_MAX_INTERRUPCAO")
    df = interruptions.join(max_hours, how="cross")
    df = df.filter(
        pl.col("delta").truediv(60 * 60) > pl.col("VL_TEMPO_MAX_INTERRUPCAO")
    )
    df = df.with_columns(pl.lit("Equipamento").alias("tipo"))
    return df


def _equipment_summary(violations: pl.DataFrame) -> pl.DataFrame:
    summary = violations.group_by(
        ["NU_CNPJ", "DT_MES", "VL_TEMPO_MAX_INTERRUPCAO", "tipo"]
    ).len("size")
    summary = summary.with_columns(
        [
            pl.col("size").eq(0).alias("cumpriu"),
            pl.format("0 ({}h)", pl.col("VL_TEMPO_MAX_INTERRUPCAO")).alias("val_esp"),
            pl.col("size").alias("val"),
        ]
    )
    return summary


def _system_mean_delta(
    interruptions: pl.DataFrame, params: pl.DataFrame
) -> pl.DataFrame:
    max_hours = _param_by_cnpj(params, TIPOS_SISTEMA, "VL_TEMPO_MAX_INTERRUPCAO")
    if max_hours.is_empty():
        return pl.DataFrame()

    per_radar = interruptions.group_by(RADAR_KEYS).agg(
        pl.col("delta").mean().alias("mean_delta")
    )
    out = per_radar.group_by("DT_MES").agg(
        pl.col("mean_delta").mean().alias("mean_mean_delta")
    )
    out = out.join(max_hours, how="cross").with_columns(
        pl.col("VL_TEMPO_MAX_INTERRUPCAO").mul(60 * 60).alias("tempo_max")
    )
    out = out.with_columns(pl.lit("Sistema").alias("tipo"))
    return out


def _system_summary(mean_delta: pl.DataFrame) -> pl.DataFrame:
    if mean_delta.is_empty():
        return pl.DataFrame()
    summary = mean_delta.rename(
        {"mean_mean_delta": "val", "VL_TEMPO_MAX_INTERRUPCAO": "val_esp"}
    )
    summary = summary.with_columns(
        [
            pl.col("val").le(pl.col("val_esp")).alias("cumpriu"),
            pl.format("0 ({}h)", pl.col("val_esp")).alias("val_esp"),
            pl.col("val"),
        ]
    ).with_columns(pl.col("val").cast(int).map_elements(format_seconds).alias("val"))
    return summary


# -- Sistema (%): availability per month vs. min allowed --


def _system_pct_summary(
    interruptions: pl.DataFrame, params: pl.DataFrame
) -> pl.DataFrame:
    min_pct = _param_by_cnpj(params, TIPOS_SISTEMA_PCT, "VL_PCT_MAX_INTERRUPCAO")

    if min_pct.is_empty():
        return pl.DataFrame()

    summary = _monthly_availability(interruptions).rename({"mean_p": "val"})
    summary = summary.join(
        min_pct.select(["NU_CNPJ", "VL_PCT_MAX_INTERRUPCAO"]),
        on="NU_CNPJ",
        how="left",
    )
    summary = summary.with_columns(
        [
            pl.col("val").round(4).mul(100).alias("val"),
            pl.col("VL_PCT_MAX_INTERRUPCAO").alias("val_esp"),
            pl.lit("Sistema (%)").alias("tipo"),
            pl.col("val").ge(pl.col("VL_PCT_MAX_INTERRUPCAO")).alias("cumpriu"),
        ]
    )
    summary = summary.with_columns(
        [
            pl.format("{:.2f}%", pl.col("val")).alias("val"),
            pl.format("{:.2f}%", pl.col("val_esp")).alias("val_esp"),
        ]
    )
    return summary


def build_param_summary(
    daily_volume: pl.DataFrame,
    params: pl.DataFrame,
    interruptions: pl.DataFrame,
) -> pl.DataFrame:
    # One row per CNPJ/month/check that applies to the concessionaire
    table = _monthly_volume(daily_volume).join(
        params[["CD_TIPO_INTERRUPCAO"]], how="cross"
    )
    table = table.with_columns(
        pl.col("CD_TIPO_INTERRUPCAO")
        .map_elements(lambda x: DS_TIPO_BY_CODE.get(x, []), pl.List(pl.String))
        .alias("tipo")
    )
    table = table.explode("tipo")

    items_to_concat = [
        _equipment_summary(_equipment_violations(interruptions, params)),
        _system_summary(_system_mean_delta(interruptions, params)),
        _system_pct_summary(interruptions, params),
    ]
    summaries = pl.concat(items_to_concat, how="diagonal_relaxed").with_columns(
        pl.col("DT_MES").dt.strftime("%Y-%m").alias("DT_MES_str")
    )
    table = table.join(summaries, how="left", on=["DT_MES", "tipo"])

    no_violations_expr = (
        (pl.col("tipo") == "Equipamento")
        & (pl.col("cumpriu").is_null())
        & (pl.col("size") > 0)
    )
    table = table.with_columns(
        pl.when(no_violations_expr)
        .then(True)
        .otherwise(pl.col("cumpriu"))
        .alias("cumpriu")
    )
    table = table.with_columns(
        pl.when(pl.col("cumpriu"))
        .then(pl.lit("Sim"))
        .otherwise(pl.lit("Não"))
        .alias("cumpriu")
    )
    table = table.drop(["size", "CD_TIPO_INTERRUPCAO"])
    return table


def _load_daily_volume(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_RADAR_QUERIES["get_daily_volume"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


def eval_params(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    company_names = get_company_names()
    interruptions = build_interruptions(
        _load_raw_interruptions(cnpj, date_range), company_names
    )
    params = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        True,
    )
    daily_volume = _load_daily_volume(cnpj, date_range)
    param_summary = build_param_summary(daily_volume, params, interruptions)
    df_eval_f = param_summary.filter(pl.col("val_esp") != "-")
    df_eval_f = df_eval_f.drop(["NU_CNPJ", "DT_MES"])
    df_eval_f = df_eval_f.with_columns(
        pl.col("DT_MES_str")
        .str.strptime(pl.Date, "%Y-%m")
        .dt.strftime("%m/%Y")
        .alias("month")
    )
    df_eval_f = df_eval_f.rename(
        {
            "val_esp": "Falhas esperadas (valor máximo)",
            "month": "Mês",
            "tipo": "Parâmetro",
            "val": "Falhas contabilizadas",
            "cumpriu": "Cumprimento",
        }
    ).drop(["DT_MES_str", "QT_CONTAGEM", "VL_TEMPO_MAX_INTERRUPCAO"])
    return df_eval_f
