from datetime import date
from pathlib import Path
from typing import Final, TypedDict

import polars as pl
import streamlit as st

from client import ch_client
from queries import get_query_result


class VitQueries(TypedDict):
    get_total_count: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :output DataFrame["QT_CONTAGEM" (int)]
    """
    get_seen_vehicle_counts: Path
    """
    :param none
    :output DataFrame["NU_CNPJ" (string), "QT_VISTO" (int)]
    """
    get_vehicle_dates: Path
    """
    :param none
    :output DataFrame["NU_CNPJ" (string), "start_date" (date), "end_date" (date)]
    """
    get_daily_data: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :output DataFrame["NU_CNPJ" (string), "DT_DIA" (date), "QT_CONTAGEM" (int)]
    """
    get_points: Path
    """
    :param cnpj (string), date_start (string#date), date_end (string#date)
    :output DataFrame[
        "NO_PONTO" (string), "DS_TIPO_PONTO" (string),
        "CG_LATITUDE" (float), "CG_LONGITUDE" (float),
        "QT_CONTAGEM" (int)
    ]
    """
    get_vit_params: Path
    """
    :param cnpj (string)
    :output DataFrame["VIT parameter fields for the latest deploy"]
    """
    get_all_coords: Path
    """
    :param none
    :output DataFrame[
        "NU_CNPJ" (string), "CD_PONTO" (int), "CG_LATITUDE" (float),
        "CG_LONGITUDE" (float), "DS_TIPO_PONTO" (string)
    ]
    """
    get_vehicle_intervals: Path
    """
    :param date_start (string#date), date_end (string#date)
    :output DataFrame[
        "NU_CNPJ" (string), "DS_PLACA" (string),
        "DT_INSTANTE_ANTERIOR" (datetime), "VL_DELTA" (int),
        "VL_DISTANCIA_KM" (float)
    ]
    """
    get_delays: Path
    """
    :param date_start (string#date), date_end (string#date)
    :output DataFrame[
        "NU_CNPJ" (string), "DS_TIPO_PONTO" (string), "CD_PONTO" (int),
        "NO_PONTO" (string), "CD_SENTIDO" (int), "NO_SENTIDO" (string),
        "DT_INSTANTE_ANTERIOR" (datetime), "DT_INSTANTE" (datetime),
        "DS_PLACA_ANTERIOR" (string), "DS_PLACA" (string), "VL_DELTA" (int)
    ]
    """
    get_parameters: Path
    """
    :param none
    :output DataFrame[
        "NU_CNPJ" (string), "VL_INTERVALO" (float),
        "VL_SOMA_QUATRO_ATRASOS" (float), "VL_VELOCIDADE_MEDIA" (float)
    ]
    """
    get_monthly_counts: Path
    """
    :param none
    :output DataFrame["NU_CNPJ" (string), "DT_MES" (string), "QT_CONTAGEM" (int)]
    """


AVAILABLE_VIT_QUERIES: Final[VitQueries] = {
    "get_total_count": Path("queries", "vit", "get_total_count.sql"),
    "get_seen_vehicle_counts": Path("queries", "vit", "get_seen_vehicle_counts.sql"),
    "get_vehicle_dates": Path("queries", "vit", "get_vehicle_dates.sql"),
    "get_daily_data": Path("queries", "vit", "get_daily_data.sql"),
    "get_points": Path("queries", "vit", "get_points.sql"),
    "get_vit_params": Path("queries", "vit", "get_vit_params.sql"),
    "get_all_coords": Path("queries", "vit", "get_all_coords.sql"),
    "get_vehicle_intervals": Path("queries", "vit", "get_vehicle_intervals.sql"),
    "get_delays": Path("queries", "vit", "get_delays.sql"),
    "get_parameters": Path("queries", "vit", "get_parameters.sql"),
    "get_monthly_counts": Path("queries", "vit", "get_monthly_counts.sql"),
}


def get_vehicle_counts(cnpj: str):
    client = ch_client()
    generic_plates = pl.from_pandas(
        client.query_df("SELECT DS_PLACA FROM BD_RAW_INTERNO.TB_PLACAS_GENERICAS")
    )["DS_PLACA"].to_list()
    vehicles = pl.from_pandas(
        client.query_df("SELECT * FROM BD_ANALYTICS_SIR.V_VIT_CADASTRO")
    ).drop("NO_FANTASIA")
    vehicles = vehicles.filter(~pl.col("DS_PLACA").is_in(generic_plates))
    counts_global = vehicles.group_by("NU_CNPJ").len(name="QT_CADASTRADO")
    counts_per = pl.from_pandas(
        client.query_df("SELECT * FROM BD_ANALYTICS_SIR.V_QUANTIDADE_VITS")
    ).drop("NO_FANTASIA")
    counts_global = counts_global.join(counts_per, how="left", on="NU_CNPJ")
    counts_seen = get_query_result(
        AVAILABLE_VIT_QUERIES["get_seen_vehicle_counts"], {}, use_polars=True
    )
    counts_global = counts_global.join(counts_seen, on="NU_CNPJ")

    count_per_cnpj = counts_per.filter(pl.col("NU_CNPJ") == cnpj)
    counts_global_cnpj = counts_global.filter(pl.col("NU_CNPJ") == cnpj)
    qtd_min = count_per_cnpj["QT_VIT"][0] if not count_per_cnpj.is_empty() else 0
    qtd_cadastro = (
        counts_global_cnpj["QT_CADASTRADO"][0]
        if not counts_global_cnpj.is_empty()
        else 0
    )
    qtd_visto = (
        counts_global_cnpj["QT_VISTO"][0] if not counts_global_cnpj.is_empty() else 0
    )
    return qtd_min, qtd_cadastro, qtd_visto


def get_dates(cnpj: str):
    vit_dates = get_query_result(
        AVAILABLE_VIT_QUERIES["get_vehicle_dates"], {}, use_polars=True
    )
    dates = vit_dates.filter(pl.col("NU_CNPJ") == cnpj)
    return (
        dates["start_date"][0].strftime("%d/%m/%Y"),
        dates["end_date"][0].strftime("%d/%m/%Y"),
    )


def get_daily_data(cnpj: str, min_day: str, max_day: str) -> pl.DataFrame:
    vit_data_days = get_query_result(
        AVAILABLE_VIT_QUERIES["get_daily_data"],
        {"cnpj": cnpj, "date_start": min_day, "date_end": max_day},
        use_polars=True,
    )
    return vit_data_days.with_columns(
        pl.col("DT_DIA").dt.strftime("%Y-%m").alias("month")
    )


def get_registered_vehicles(cnpj: str) -> pl.DataFrame:
    client = ch_client()
    generic_plates = pl.from_pandas(
        client.query_df("SELECT DS_PLACA FROM BD_RAW_INTERNO.TB_PLACAS_GENERICAS")
    )["DS_PLACA"].to_list()
    vehicles = pl.from_pandas(
        client.query_df("SELECT * FROM BD_ANALYTICS_SIR.V_VIT_CADASTRO")
    ).drop("NO_FANTASIA")
    vehicles = vehicles.filter(
        pl.col("NU_CNPJ").eq(cnpj) & ~pl.col("DS_PLACA").is_in(generic_plates)
    )
    return vehicles.drop("NU_CNPJ")


def get_vit_points(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_VIT_QUERIES["get_points"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


vit_params_desc = {
    "vel_med": "Os veículos deverão percorrer o trecho concedido com velocidade média de {x} km/h.",
    "soma_quatro_atrasos": "Em qualquer ponto da rodovia, a somatória dos atrasos com relação à frequência estabelecida para a inspeção de tráfego, a cada 4 viaturas, não poderá ser superior a {x} minutos.",
    "it": "Os serviços de Inspeção de tráfego deverão realizar ciclos com tempo médio de circulação de {x} minutos, em condições normais de operação.",
}


def get_vit_params(cnpj: str) -> pl.DataFrame:
    params = get_query_result(
        AVAILABLE_VIT_QUERIES["get_vit_params"],
        {"cnpj": cnpj},
        use_polars=True,
    )

    messages = []
    if params["vel_med"].null_count() < params.height:
        messages.append(
            f"- **Velocidade média (VMéd)**: {vit_params_desc['vel_med'].format(x=params['vel_med'][0])}"
        )
    if params["soma_quatro_atrasos"].null_count() < params.height:
        messages.append(
            f"- **Soma de quatro atrasos consecutivos (Σ4)**: {vit_params_desc['soma_quatro_atrasos'].format(x=params['soma_quatro_atrasos'][0])}"
        )
    if params["it"].null_count() < params.height:
        messages.append(
            f"- **Intervalo de tempo (IT)**: {vit_params_desc['it'].format(x=params['it'][0])}"
        )
    st.markdown("\n".join(messages))
    return params
