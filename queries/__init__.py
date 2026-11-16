from pathlib import Path
from typing import Literal, overload

import polars as pl
import streamlit as st
from pandas import DataFrame as PandasDataFrame
from polars import DataFrame as PolarsDataFrame
from polars import from_pandas

from client import ch_client
from constants import DICT_TIPO_VEICULO_RECURSO


def get_sql_template(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        sql_template = f.read()
    return sql_template


@overload
def get_query_result(
    path: Path,
    inputs: dict[str, str],
    use_polars: Literal[True] = True,
) -> PolarsDataFrame: ...


@overload
def get_query_result(
    path: Path,
    inputs: dict[str, str],
    use_polars: Literal[False] = False,
) -> PandasDataFrame: ...


def get_query_result(
    path: Path,
    inputs: dict[str, str],
    use_polars: bool = False,
) -> PandasDataFrame | PolarsDataFrame:
    sql_template = get_sql_template(path)
    sql_query = sql_template.format(**inputs)
    pd_df = ch_client().query_df(sql_query)
    if use_polars:
        return PolarsDataFrame(pd_df)
    return pd_df


DICT_NAME_TO_FILE = {
    "zeroing_data": "queries/zeroing_data.sql",
    "get_data": "queries/full_stats.sql",
    "stats_region": "queries/stats_region.sql",
}


def get_template_str(name: str) -> str:
    file_name = DICT_NAME_TO_FILE.get(name, None)
    if file_name is None:
        raise ValueError("Invalid SQL handle")
    with open(file_name, "r", encoding="utf-8") as f:
        result = f.read()
        return result


@st.cache_data
def get_zeroing_data(resolution: int) -> PolarsDataFrame:
    template = get_template_str("zeroing_data")
    applied_template = template.format(resolution=resolution)
    return PolarsDataFrame(from_pandas(ch_client().query_df(applied_template)))


def get_raw_data_for_hexagons(
    cnpj: str,
    resolution: int,
    recurso: str,
    hexagons: list[str],
    only_zeroeds: bool = True,
):
    hexagon_list_as_str = "({})".format(",".join([f"'{h}'" for h in hexagons]))
    filters_str = [
        f"NU_CNPJ = '{cnpj}'",
        f"DS_TIPO_SERVICO = '{DICT_TIPO_VEICULO_RECURSO[recurso]}'",
        f"DS_TIPO_VEICULO_RECURSO = '{recurso}'",
        f"hex(geoToH3(CG_LATITUDE_ATENDIMENTO, CG_LONGITUDE_ATENDIMENTO, {resolution})) IN {hexagon_list_as_str}",
    ]

    if only_zeroeds:
        filter_time = "CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS < 1"
        filters_str.append(filter_time)

    total_filter = " AND\n".join(filters_str)

    sql = f"""
    SELECT
        CD_GUID AS ID,
        CD_RODOVIA AS Rodovia,
        DS_PLACA_RECURSO AS Placa_Recurso,
        DT_ACIONAMENTO_RECURSO AS `Momento_Acionamento`,
        DT_CHEGADA_LOCAL AS `Momento_Chegada`
    FROM
        BD_ANALYTICS_SIR.V_ATENDIMENTO_ACIONAMENTOS
    WHERE {total_filter}
    ORDER BY `Momento_Acionamento`
    """

    data = pl.DataFrame(pl.from_pandas(ch_client().query_df(sql)))
    return data


def get_stats_region(
    cnpj: str, tipo_recurso: str, resolution: int, hexagons: list[str]
):
    hexagon_list_as_str = "({})".format(",".join([f"'{h}'" for h in hexagons]))
    tipo_servico = DICT_TIPO_VEICULO_RECURSO[tipo_recurso]
    template = get_template_str("stats_region")
    applied_template = template.format(
        resolution=resolution,
        cnpj=cnpj,
        tipo_servico=tipo_servico,
        tipo_recurso=tipo_recurso,
        hexagon_list_str=hexagon_list_as_str,
    )
    data = PolarsDataFrame(from_pandas(ch_client().query_df(applied_template)))
    return {
        "avgInRegion": float(data["Media_Regiao"].item(0)),
        "avgTotal": float(data["Media_Total"].item(0)),
        "minInRegion": float(data["Min_Regiao"].item(0)),
        "minTotal": float(data["Min_Total"].item(0)),
        "maxInRegion": float(data["Max_Regiao"].item(0)),
        "maxTotal": float(data["Max_Total"].item(0)),
        "stdInRegion": float(data["DesvioPadrao_Regiao"].item(0)),
        "stdTotal": float(data["DesvioPadrao_Total"].item(0)),
    }


@st.cache_data
def get_data_with_res(resolution: int):
    template = get_template_str("get_data")
    applied_template = template.format(resolution=resolution)
    return PolarsDataFrame(from_pandas(ch_client().query_df(applied_template)))
