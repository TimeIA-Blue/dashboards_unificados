from collections.abc import Hashable
from typing import Any, TypedDict

import polars as pl
from numpy import uint16
from pandas import DataFrame as PandasDataFrame
from pandas import Timestamp

from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES

TIPO_EQUIPAMENTO = 1
TIPO_SISTEMA = 2
DS_TIPO_BY_CODE = {TIPO_SISTEMA: ["Sistema"], TIPO_EQUIPAMENTO: ["Equipamento"]}


def format_seconds(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}min")
    if s > 0 or not parts:
        parts.append(f"{s}s")
    return "".join(parts)


def _load_praca_locations(client) -> pl.DataFrame:
    return pl.DataFrame(
        client.query_df(
            """
        SELECT
            CD_PRACA_PEDAGIO AS CD_PRACA,
            CG_LATITUDE,
            CG_LONGITUDE
        FROM
            BD_ANALYTICS_SIR.V_PEDAGIO_INFO
        """
        )
    )


def build_interruptions(raw: pl.DataFrame) -> pl.DataFrame:
    return raw.with_columns(
        [
            pl.col("VL_DELTA").truediv(3600).alias("VL_DELTA_HORA"),
            pl.col("VL_DELTA")
            .map_elements(format_seconds, pl.String)
            .alias("DS_DELTA_FORMATADO"),
        ]
    )


def dataframe_to_csv(df: PandasDataFrame) -> bytes:
    download_df = df.copy()
    for column in download_df.select_dtypes(include=["datetime", "datetimetz"]):
        download_df[column] = download_df[column].dt.strftime("%d/%m/%Y %H:%M:%S")
    for column in download_df.select_dtypes(include=["float"]):
        download_df[column] = download_df[column].round(2)
    return download_df.to_csv(index=False).encode("utf-8")


pedagio_types = {1: "Equipamento", 2: "Sistema"}

pedagio_exp_formats = {
    "Equipamento": """Indisponibilidades sofridas por uma praça não podem ultrapassar {x} horas contínuas.
    O valor esperado descrito nas tabelas é 0 (zero) pois idealmente espera-se que as praças não sofram indisponibilidades.""",
    "Sistema": "A média de indisponibilidade dos elementos que compõem o sistema não pode ultrapassar {x} horas mensais.",
}


def get_company_params(cnpj: str):
    params = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=False,
    )

    print("LEN PARAMS", len(params))

    if params.empty:
        return "Não há parâmetros operacionais definidos no Programa de Exploração da Rodovia (PER) desta concessionária."

    params["CD_TIPO_INTERRUPCAO"] = params["CD_TIPO_INTERRUPCAO"].map(pedagio_types)

    out = list[str]()

    for p in params.to_dict(orient="records"):
        value: uint16
        if p["CD_TIPO_INTERRUPCAO"] in ["Equipamento", "Sistema"]:
            value = p["VL_TEMPO_MAX_INTERRUPCAO"]
            msg = f"* **{p['CD_TIPO_INTERRUPCAO']}**: " + pedagio_exp_formats[
                p["CD_TIPO_INTERRUPCAO"]
            ].format(x=value)
        else:
            msg = "Não há parâmetros operacionais definidos no Programa de Exploração da Rodovia (PER) desta concessionária."

        out.append(msg)

    return "\n".join(out)


class GetGapsReturnDict(TypedDict):
    group: int
    start: Timestamp
    end: Timestamp
    length: int


def get_gaps(
    cnpj: str,
) -> tuple[PandasDataFrame, Timestamp, Timestamp, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_gaps"],
        {"cnpj": cnpj},
        use_polars=False,
    )

    t["is_zero"] = t["QT_CONTAGEM"] == 0
    t["group"] = (t["is_zero"] != t["is_zero"].shift()).cumsum()

    min_date: Timestamp = t["DT_DIA"].min()
    max_date: Timestamp = t["DT_DIA"].max()

    where_zero: PandasDataFrame = t[t["is_zero"]]
    gaps = (
        where_zero.groupby("group")
        .agg(
            start=("DT_DIA", "min"),
            end=("DT_DIA", "max"),
            length=("DT_DIA", "count"),
        )
        .reset_index(drop=True)
    )

    # TypedDict is a mapping, dict is more strict. However, just change the way it is accessed and its fine.
    gaps_as_dicts: list[GetGapsReturnDict] = gaps.to_dict(orient="records")  # ty: ignore[invalid-assignment]

    return t, min_date, max_date, gaps_as_dicts


def get_total_equipment(cnpj: str) -> int:
    t = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_total_tolls"], {"cnpj": cnpj}, use_polars=False
    )
    return t["QT_TOTAL_PRACAS"].iloc[0]


def get_failing_equipment(cnpj: str) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_failing_tolls"],
        {"cnpj": cnpj},
        use_polars=False,
    )
    return t.to_dict(orient="records")


def get_equipment_map(cnpj: str) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_toll_map"], {"cnpj": cnpj}, use_polars=False
    )
    return t.to_dict(orient="records")
