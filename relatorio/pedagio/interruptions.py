from datetime import date

import polars as pl

from client import ch_client
from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES
from relatorio.pedagio.helpers import (
    _load_praca_locations,
    build_interruptions,
    format_seconds,
)


def eval_interruptions(
    cnpj: str, date_range: tuple[date, date]
) -> tuple[pl.DataFrame, int, int, str, str, pl.DataFrame]:
    client = ch_client()
    raw_interruptions = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_interruptions"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        True,
    )
    locations = _load_praca_locations(client)
    interruptions = build_interruptions(raw_interruptions)
    interLocal = interruptions.join(locations, on="CD_PRACA", how="left")
    interLocal = interLocal.with_columns(
        pl.col("DT_MES").str.strptime(pl.Date, "%Y-%m").dt.strftime("%m/%Y")
    )
    mean_inter = interLocal["VL_DELTA"].mean()
    mean_inter = 0 if None else mean_inter
    dev_inter = interLocal["VL_DELTA"].std()
    dev_inter = 0 if None else dev_inter

    top_equips = interLocal.group_by(["NO_PRACA"]).agg(
        [
            pl.col("VL_DELTA").mean().alias("VL_DELTA_MEDIO"),
            pl.col("VL_DELTA").count().alias("QT_QUANTIDADE_INTERRUP"),
        ]
    )
    top_equips = top_equips.sort("QT_QUANTIDADE_INTERRUP", descending=True)
    top_equips = top_equips.with_columns(
        pl.col("VL_DELTA_MEDIO").map_elements(format_seconds, pl.String)
    )
    top_equips = top_equips.rename(
        {
            "NO_PRACA": "Nome da praça",
            "VL_DELTA_MEDIO": "Duração média das interrupções",
            "QT_QUANTIDADE_INTERRUP": "Número de interrupções",
        }
    )

    interLocal = interLocal.drop(
        [
            "NU_CNPJ",
            "VL_DELTA",
            "VL_DELTA_HORA",
            "VL_TOLERANCIA",
            "CG_LATITUDE",
            "CG_LONGITUDE",
        ]
    )
    interLocal = interLocal.rename(
        {
            "CD_PRACA": "Código da praça",
            "NO_PRACA": "Nome da praça",
            "DT_INSTANTE_ANTERIOR": "Data/hora início da interrupção",
            "DT_INSTANTE": "Data/hora fim da interrupção",
            "DT_MES": "Mês",
            "DS_DELTA_FORMATADO": "Duração da interrupção",
        }
    )

    total_inter = len(interLocal)
    equip_count = interLocal["Código da praça"].n_unique()
    mean_inter = format_seconds(int(mean_inter))  # ty: ignore[invalid-argument-type]
    dev_inter = format_seconds(int(dev_inter))  # ty: ignore[invalid-argument-type]

    return interLocal, total_inter, equip_count, mean_inter, dev_inter, top_equips
