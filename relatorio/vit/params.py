from collections import defaultdict
from datetime import date

import polars as pl
import streamlit as st

from queries import get_query_result
from queries.general import get_company_names
from queries.vit import AVAILABLE_VIT_QUERIES

MONTH_KEYS = ["NU_CNPJ", "DT_MES"]
POINT_KEYS = [
    "NU_CNPJ",
    "DT_MES",
    "DS_TIPO_PONTO",
    "NO_PONTO",
    "CD_SENTIDO",
    "NO_SENTIDO",
]
BATCH_SIZE = 4
VMED_TOLERANCE_KMH = 10


def _load_all_coords() -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_all_coords"], {}, use_polars=True
    )


def _load_vehicle_intervals(date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_vehicle_intervals"],
        {
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


def _load_raw_atrasos(date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_delays"],
        {
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


def _load_vit_params() -> pl.DataFrame:
    """Parameters of the latest deploy (one row per concessionaire)."""
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_parameters"], {}, use_polars=True
    )


def _load_monthly_counts() -> pl.DataFrame:
    """Sightings per concessionaire per month (all history)."""
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_monthly_counts"], {}, use_polars=True
    )


def _param(params: pl.DataFrame, column: str) -> pl.DataFrame:
    """[NU_CNPJ, column] for concessionaires that define this parameter."""
    return params.select(["NU_CNPJ", column]).drop_nulls(column)


def build_atrasos(
    raw: pl.DataFrame,
    it_params: pl.DataFrame,
    coords: pl.DataFrame,
    company_names: dict[str, str],
) -> pl.DataFrame:
    """Only the delays: intervals longer than the allowed IT.

    Concessionaires without delays are handled when building the summaries.
    """
    df = raw.join(it_params, how="left", on="NU_CNPJ").with_columns(
        (pl.col("VL_INTERVALO") * 60).alias("VL_INTERVALO_SEGUNDOS")
    )
    df = df.filter(pl.col("VL_DELTA") > pl.col("VL_INTERVALO_SEGUNDOS"))
    df = df.with_columns(
        [
            (pl.col("VL_DELTA") - pl.col("VL_INTERVALO_SEGUNDOS"))
            .clip(lower_bound=0)
            .alias("VL_ATRASO_SEGUNDOS"),
            pl.col("DT_INSTANTE_ANTERIOR").dt.strftime("%Y-%m").alias("DT_MES"),
            (
                (pl.col("VL_DELTA") - pl.col("VL_INTERVALO_SEGUNDOS")).clip(
                    lower_bound=0
                )
                / 60
            ).alias("atraso_mins"),
            pl.col("NU_CNPJ")
            .replace_strict(company_names, default=None)
            .alias("fantasia"),
        ]
    )

    # NOTE: joins on CNPJ + point type only, NOT on CD_PONTO. A concessionaire
    # with N points of a type gets every delay repeated N times. Kept as in the
    # original; see the notes on this refactor.
    return df.join(coords, how="left", on=["NU_CNPJ", "DS_TIPO_PONTO"])


def build_sum4_violations(
    atrasos: pl.DataFrame, sum_params: pl.DataFrame
) -> pl.DataFrame:
    """Σ4: groups each series' delays into consecutive batches of 4 (in time
    order; incomplete batches are discarded) and keeps the batches whose summed
    delay exceeds the concessionaire's limit."""
    series = atrasos.select(
        POINT_KEYS + ["DT_INSTANTE_ANTERIOR", "VL_ATRASO_SEGUNDOS"]
    ).sort(POINT_KEYS + ["DT_INSTANTE_ANTERIOR"])
    series = series.with_columns(
        (
            (pl.col("VL_ATRASO_SEGUNDOS").cum_count().over(POINT_KEYS) - 1)
            // BATCH_SIZE
        ).alias("batch_id")
    )
    batch_keys = POINT_KEYS + ["batch_id"]
    sums = (
        series.group_by(batch_keys)
        .agg(
            [
                pl.len().alias("batch_size"),
                pl.col("VL_ATRASO_SEGUNDOS").sum().alias("VL_SOMA_ATRASOS_SEGUNDOS"),
            ]
        )
        .filter(pl.col("batch_size") == BATCH_SIZE)
        .drop("batch_size")
        .join(sum_params, how="left", on="NU_CNPJ")
    )
    return sums.filter(
        pl.col("VL_SOMA_ATRASOS_SEGUNDOS") > pl.col("VL_SOMA_QUATRO_ATRASOS") * 60
    )


def build_vel_med(intervals: pl.DataFrame) -> pl.DataFrame:
    """Mean speed per vehicle per month."""
    return (
        intervals.with_columns(
            [
                (pl.col("VL_DISTANCIA_KM") / (pl.col("VL_DELTA") / 3_600)).alias(
                    "VL_VELOCIDADE_MEDIA"
                ),
                pl.col("DT_INSTANTE_ANTERIOR").dt.strftime("%Y-%m").alias("DT_MES"),
            ]
        )
        .group_by(["NU_CNPJ", "DS_PLACA", "DT_MES"])
        .agg(pl.col("VL_VELOCIDADE_MEDIA").mean())
    )


def build_base_table(
    monthly_counts: pl.DataFrame, date_range: tuple[date, date]
) -> pl.DataFrame:
    """Every concessionaire x every month of the range, with its sighting count."""
    min_day, max_day = date_range
    start_month = min_day.replace(day=1)
    end_month = max_day.replace(day=1)
    months = pl.date_range(
        start_month, end_month, interval="1mo", eager=True
    ).dt.strftime("%Y-%m")
    cnpjs = monthly_counts.select("NU_CNPJ").unique()
    grid = cnpjs.join(pl.DataFrame({"DT_MES": months}), how="cross")
    return grid.join(monthly_counts, how="left", on=MONTH_KEYS).fill_null(0)


def _status(met: pl.Expr, has_data: pl.Expr) -> pl.Expr:
    """'-' when there is no data, otherwise 'Sim' if met else 'Não'."""
    return (
        pl.when(~has_data)
        .then(pl.lit("-"))
        .when(met)
        .then(pl.lit("Sim"))
        .otherwise(pl.lit("Não"))
    )


def _violation_count_summary(
    base: pl.DataFrame,
    violations: pl.DataFrame,
    params: pl.DataFrame,
    param_column: str,
    tipo: str,
) -> pl.DataFrame:
    """Expected: zero violations in the month."""
    counts = violations.group_by(MONTH_KEYS).agg(pl.len().alias("VL_VALOR"))
    return (
        base.join(counts, how="left", on=MONTH_KEYS)
        .join(params, on="NU_CNPJ")
        .with_columns(
            [
                pl.col("VL_VALOR").fill_null(0),
                pl.format("0 ({}min)", pl.col(param_column)).alias("VL_VALOR_ESPERADO"),
                _status(
                    met=pl.col("VL_VALOR").fill_null(0) <= 0,
                    has_data=pl.col("QT_CONTAGEM") > 0,
                ).alias("cumpriu"),
                pl.lit(tipo).alias("tipo"),
            ]
        )
        .drop(param_column)
    )


def _vmed_summary(
    base: pl.DataFrame, vel_med: pl.DataFrame, vmed_params: pl.DataFrame
) -> pl.DataFrame:
    """Expected: monthly mean speed within ±10 km/h of the parameter."""
    monthly = vel_med.group_by(MONTH_KEYS).agg(
        pl.col("VL_VELOCIDADE_MEDIA").mean().alias("VL_VALOR")
    )
    expected = vmed_params.rename({"VL_VELOCIDADE_MEDIA": "VL_ESPERADO"})
    return (
        base.join(monthly, how="left", on=MONTH_KEYS)
        .join(expected, on="NU_CNPJ")
        .with_columns(
            [
                pl.col("VL_VALOR").fill_null(0).round(2),
                pl.format(
                    "{} ± {} km/h", pl.col("VL_ESPERADO"), VMED_TOLERANCE_KMH
                ).alias("VL_VALOR_ESPERADO"),
                _status(
                    met=pl.col("VL_VALOR")
                    .fill_null(0)
                    .is_between(
                        pl.col("VL_ESPERADO") - VMED_TOLERANCE_KMH,
                        pl.col("VL_ESPERADO") + VMED_TOLERANCE_KMH,
                    ),
                    has_data=pl.col("QT_CONTAGEM") > 0,
                ).alias("cumpriu"),
                pl.lit("VMéd").alias("tipo"),
            ]
        )
        .drop("VL_ESPERADO")
    )


def build_full_summary(
    base: pl.DataFrame,
    atrasos: pl.DataFrame,
    sum4_violations: pl.DataFrame,
    vel_med: pl.DataFrame,
    params: pl.DataFrame,
) -> pl.DataFrame:
    items_to_concat = [
        _violation_count_summary(
            base, atrasos, _param(params, "VL_INTERVALO"), "VL_INTERVALO", "IT"
        ),
        _violation_count_summary(
            base,
            sum4_violations,
            _param(params, "VL_SOMA_QUATRO_ATRASOS"),
            "VL_SOMA_QUATRO_ATRASOS",
            "Σ4",
        ),
        _vmed_summary(base, vel_med, _param(params, "VL_VELOCIDADE_MEDIA")),
    ]
    full = pl.concat(
        items_to_concat,
        how="vertical_relaxed",
    )
    return full.with_columns(pl.col("VL_VALOR").round().cast(pl.Int64)).drop(
        "QT_CONTAGEM"
    )


def get_company_eval(cnpj: str, date_range: tuple[date, date]):
    steps = 5
    progress = st.progress(0, text="Estabelecendo conexão com o banco de dados...")

    progress.progress(1 / steps, text="Carregando nomes das concessionárias...")
    company_names = get_company_names()

    progress.progress(2 / steps, text="Carregando dados geográficos...")
    coords = _load_all_coords()

    progress.progress(3 / steps, text="Carregando dados de distância...")
    vel_med = build_vel_med(_load_vehicle_intervals(date_range))

    progress.progress(4 / steps, text="Calculando cumprimento de parâmetros...")
    params = _load_vit_params()
    atrasos = build_atrasos(
        _load_raw_atrasos(date_range),
        _param(params, "VL_INTERVALO"),
        coords,
        company_names,
    )
    sum4_violations = build_sum4_violations(
        atrasos, _param(params, "VL_SOMA_QUATRO_ATRASOS")
    )
    base = build_base_table(_load_monthly_counts(), date_range)

    progress.progress(5 / steps, text="Finalizando cálculos...")
    full_summary = build_full_summary(base, atrasos, sum4_violations, vel_med, params)

    # Presentation step: normalize CNPJ only after every join above is done.
    full_summary = full_summary.with_columns(pl.col("NU_CNPJ").cast(pl.String))
    atrasos = atrasos.with_columns(pl.col("NU_CNPJ").cast(pl.String))

    progress.empty()

    df_company = full_summary.filter(pl.col("NU_CNPJ") == cnpj)
    checks = {"none": [], "all": [], "partial": []}
    months = defaultdict(list)

    for row in df_company.iter_rows(named=True):
        if row["cumpriu"] in {"Não", "Sim", "-"}:
            months[row["DT_MES"]].append(row["cumpriu"])

    for month, values in months.items():
        if all(value == "Não" for value in values):
            checks["none"].append(month)
        elif all(value == "Sim" for value in values):
            checks["all"].append(month)
        else:
            checks["partial"].append(month)

    for key, values in checks.items():
        checks[key] = [f"{month[5:7]}/{month[0:4]}" for month in values]

    atrasos_company = atrasos.filter(pl.col("NU_CNPJ") == cnpj)
    mean_atrasos = atrasos_company.select(
        pl.col("atraso_mins").mean().round(0).fill_null(0).cast(pl.Int64)
    ).item()
    std_atrasos = atrasos_company.select(
        pl.col("atraso_mins").std().round(0).fill_null(0).cast(pl.Int64)
    ).item()

    return df_company, checks, mean_atrasos, std_atrasos, atrasos_company
