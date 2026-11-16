import datetime
from collections.abc import Hashable, Mapping
from datetime import date
from typing import Any

import pandas as pd
import polars as pl
import streamlit as st
from numpy import uint16
from pandas._libs import Timestamp
from pandas.core.frame import DataFrame

from client import ch_client
from queries import get_query_result
from queries.sat import AVAILABLE_SAT_QUERIES, SAT_GET_AVAILABLE_COMPANIES
from relatorio import GetGapsReturnDict
from relatorio.reporter import SubReporter, SubReportSection
from spotfire import format_seconds

VERIFY_SAT_AGREEMENT_EXPR = (
    pl.when(pl.col("CD_TIPO_INTERRUPCAO").is_in([2, 3, 5]))
    .then(
        pl.when(pl.col("MAX_DOWNTIME_SAT") <= pl.col("VL_TEMPO_MAX_INTERRUPCAO"))
        .then(pl.lit(1))
        .otherwise(pl.lit(-1))
    )
    .otherwise(pl.lit(0))
)

VERIFY_CNPJ_AGREEMENT_EXPR = (
    pl.when(pl.col("CD_TIPO_INTERRUPCAO").is_in([1, 3]))
    .then(
        pl.when(pl.col("MEAN_DOWNTIME_CNPJ") <= pl.col("VL_TEMPO_MAX_INTERRUPCAO"))
        .then(pl.lit(1))
        .otherwise(pl.lit(-1))
    )
    .when(pl.col("CD_TIPO_INTERRUPCAO").is_in([4, 5]))
    .then(
        pl.when(pl.col("MEAN_UPTIME_CNPJ") >= pl.col("VL_PCT_MAX_INTERRUPCAO") / 100)
        .then(pl.lit(1))
        .otherwise(pl.lit(-1))
    )
    .otherwise(pl.lit(0))
)

STATUS_CODE_TO_STR = {
    -1: "Não",
    0: "Não verificado",
    1: "Sim",
}


@st.cache_data
def sat_available_companies():
    companies = pl.DataFrame(ch_client().query_df(SAT_GET_AVAILABLE_COMPANIES))
    return companies


sat_types = {
    1: "Sistema",
    2: "Equipamento",
    3: "Sistema e Equipamento",
    4: "Sistema (%)",
    5: "Sistema (%) e Equipamento",
}

sat_exp_formats = {
    "Sistema": "A média de indisponibilidade dos elementos que compõem o sistema não pode ultrapassar {x} horas mensais.",
    "Equipamento": """Indisponibilidades sofridas por um equipamento não podem ultrapassar {x} horas contínuas.
    O valor esperado descrito nas tabelas é 0 (zero) pois idealmente espera-se que os equipamentos não sofram indisponibilidades.""",
    "Sistema e Equipamento": """Indisponibilidades sofridas por um equipamento não podem ultrapassar {x} horas contínuas.
    Além disso, a média de indisponibilidade dos elementos que compõem o sistema não pode ultrapassar {x} horas mensais.""",
    "Sistema (%)": "A média percentual de disponibilidade do sistema deve ser igual ou superior a {x}%.",
    "Sistema (%) e Equipamento": """Indisponibilidades sofridas por um equipamento não podem ultrapassar {x} horas contínuas.
    Além disso, a média percentual de disponibilidade do sistema deve ser igual ou superior a {x}%.""",
}


def get_gaps(
    cnpj: str,
    date_range: tuple[date, date],
) -> tuple[DataFrame, Timestamp, Timestamp, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_SAT_QUERIES["get_gaps"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )

    t["is_zero"] = t["QT_CONTAGEM"] == 0
    t["group"] = (t["is_zero"] != t["is_zero"].shift()).cumsum()

    min_date: pd.Timestamp = t["DT_DIA"].min()
    max_date: pd.Timestamp = t["DT_DIA"].max()

    where_zero: DataFrame = t[t["is_zero"]]
    gaps = (
        where_zero.groupby("group")
        .agg(start=("DT_DIA", "min"), end=("DT_DIA", "max"), length=("DT_DIA", "count"))
        .reset_index(drop=True)
    )

    gaps_as_dicts: list[GetGapsReturnDict] = gaps.to_dict(orient="records")  # ty: ignore[invalid-assignment]

    return t, min_date, max_date, gaps_as_dicts


def sat_get_total_equipment(cnpj: str, date_range: tuple[date, date]) -> int:
    result = get_query_result(
        AVAILABLE_SAT_QUERIES["get_total_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    total_eq: int = result["QT_TOTAL_EQUIPAMENTO"].item()
    return total_eq


def sat_get_failing_equipment(
    cnpj: str, date_range: tuple[date, date]
) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_SAT_QUERIES["get_failing_equipment"],
        {
            "cnpj": cnpj,
            "threshold": "1000",
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    return t.to_dict(orient="records")


def sat_get_params_description(cnpj: str):
    params = get_query_result(
        AVAILABLE_SAT_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=False,
    )

    equipment_level: bool = False
    system_level: bool = False
    for val in [2, 3, 5]:
        if val in params["CD_TIPO_INTERRUPCAO"].values:
            equipment_level = True
            break
    for val in [1, 3, 4, 5]:
        if val in params["CD_TIPO_INTERRUPCAO"].values:
            system_level = True
            break

    params["CD_TIPO_INTERRUPCAO"] = params["CD_TIPO_INTERRUPCAO"].map(sat_types)
    out = list[str]()

    # Pyright can't infer the keys in the object
    for p in params.to_dict(orient="records"):
        value: uint16
        if p["CD_TIPO_INTERRUPCAO"] in ["Equipamento", "Sistema"]:
            value = p["VL_TEMPO_MAX_INTERRUPCAO"]
            msg = f"* **{p['CD_TIPO_INTERRUPCAO']}**: " + sat_exp_formats[
                p["CD_TIPO_INTERRUPCAO"]
            ].format(x=value)
        else:
            value = p["VL_PCT_MAX_INTERRUPCAO"]
            msg = f"* **{p['CD_TIPO_INTERRUPCAO']}**: " + sat_exp_formats[
                p["CD_TIPO_INTERRUPCAO"]
            ].format(x=value)

        out.append(msg)

    return "\n".join(out), (equipment_level, system_level)


def sat_get_equipment_map(
    cnpj: str, date_range: tuple[date, date]
) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_SAT_QUERIES["get_equipment_map"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    return t.to_dict(orient="records")


def sat_get_downtimes(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    return get_query_result(
        AVAILABLE_SAT_QUERIES["get_formulaic_downtimes"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )


def sat_eval_params_system(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    params_pl = get_query_result(
        AVAILABLE_SAT_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=True,
    )
    downtimes_sat_pl = sat_get_downtimes(cnpj, date_range)
    n_sats_pl = get_query_result(
        AVAILABLE_SAT_QUERIES["get_total_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )
    n_sats: int = n_sats_pl["total_equipment"].item()

    stats_cnpj_pl = downtimes_sat_pl.group_by("DT_MES").agg(
        [
            pl.mean("DIFF_HOR").alias("MEAN_DOWNTIME_CNPJ"),
            (1 - (pl.sum("DIFF_HOR") / (n_sats * 720))).alias("MEAN_UPTIME_CNPJ"),
            pl.lit(n_sats).alias("N_SATS"),
        ]
    )
    agreements_cnpj_pl = (
        stats_cnpj_pl.join(params_pl, how="cross")
        .with_columns(VERIFY_CNPJ_AGREEMENT_EXPR.alias("Status"))
        .with_columns(pl.col("Status").replace_strict(STATUS_CODE_TO_STR))
        .rename(
            {
                "DT_MES": "Mês",
                "CD_TIPO_INTERRUPCAO": "Parâmetro",
                "VL_TEMPO_MAX_INTERRUPCAO": "Valor esperado",
                "VL_PCT_MAX_INTERRUPCAO": "Valor esperado (%)",
                "MEAN_DOWNTIME_CNPJ": "Duração média",
                "MEAN_UPTIME_CNPJ": "% de disponibilidade",
            }
        )
        .with_columns(pl.col("Parâmetro").replace_strict(sat_types))
    )
    agreements_cnpj_pl = agreements_cnpj_pl.drop(
        [
            "cnpj",
            "N_SATS",
        ]
    )
    if agreements_cnpj_pl["Valor esperado (%)"].is_null().all():
        agreements_cnpj_pl = agreements_cnpj_pl.drop(["Valor esperado (%)"])

    return agreements_cnpj_pl


def sat_eval_params_equipment_months(
    cnpj: str, date_range: tuple[date, date]
) -> pl.DataFrame | None:
    params_pl = get_query_result(
        AVAILABLE_SAT_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=True,
    )
    range_pl = get_query_result(
        AVAILABLE_SAT_QUERIES["get_date_range"],
        inputs={
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )

    downtimes_sat_pl = sat_get_downtimes(cnpj, date_range)
    if downtimes_sat_pl.is_empty():
        if params_pl.is_empty():
            return None
        else:
            instante_inicio = range_pl["INSTANTE_INICIO"].item()
            instante_fim = range_pl["INSTANTE_FIM"].item()
            empty_result = (
                range_pl.select(
                    pl.date_range(
                        instante_inicio,
                        instante_fim,
                        interval="1mo",
                        closed="left",
                    )
                    .explode()
                    .alias("DT_MES")
                )
                .join(params_pl, how="cross")
                .with_columns(
                    pl.lit(0).alias("MAX_DOWNTIME_SAT")
                )  # no downtimes recorded
                .with_columns(VERIFY_SAT_AGREEMENT_EXPR.alias("Status"))
                .with_columns(
                    pl.col("Status").map_elements(
                        lambda x: STATUS_CODE_TO_STR[x],
                        return_dtype=pl.Utf8,
                    )
                )
                .rename(
                    {
                        "DT_MES": "Mês",
                        "CD_TIPO_INTERRUPCAO": "Parâmetro",
                        "VL_TEMPO_MAX_INTERRUPCAO": "Valor esperado",
                        "VL_PCT_MAX_INTERRUPCAO": "Valor esperado (%)",
                    }
                )
            )
            return empty_result
    stats_sat_pl = (
        downtimes_sat_pl.group_by(
            [
                "CD_SAT",
                "DT_MES",
            ]
        )
        .agg(
            pl.max("DIFF_HOR").alias("MAX_DOWNTIME_SAT"),
        )
        .join(params_pl, how="cross")
        .with_columns(VERIFY_SAT_AGREEMENT_EXPR)
    )
    agreements_sat_pl = (
        stats_sat_pl.join(params_pl, how="cross")
        .with_columns(VERIFY_SAT_AGREEMENT_EXPR.alias("Status"))
        .with_columns(
            pl.col("Status").map_elements(
                lambda x: STATUS_CODE_TO_STR[x],
                return_dtype=pl.Utf8,
            )
        )
        .rename(
            {
                "DT_MES": "Mês",
                "CD_TIPO_INTERRUPCAO": "Parâmetro",
                "VL_TEMPO_MAX_INTERRUPCAO": "Valor esperado",
                "VL_PCT_MAX_INTERRUPCAO": "Valor esperado (%)",
            }
        )
    )
    agreements_grouped = agreements_sat_pl.group_by("Mês").agg(
        [
            pl.col("Parâmetro").first().replace_strict(sat_types).alias("Parâmetro"),
            pl.col("Valor esperado").first().alias("Valor esperado"),
            (pl.col("Status") == "Não").sum().alias("Não"),
            (pl.col("Status") == "Sim").sum().alias("Sim"),
        ]
    )
    return agreements_grouped


def sat_get_performance_description(df: pl.DataFrame, normalize: bool = True) -> str:
    def eval_mes(row: Mapping[Hashable, Any]):
        if row["Sim"] > 0:
            if row["Não"] > 0:
                return "Cumprimento parcial (ao menos um parâmetro cumprido)"
            else:
                return "Cumprimento total (todos os parâmetros cumpridos)"
        if row["Não"] > 0:
            return "Não cumprimento (todos os parâmetros descumpridos)"
        else:
            return "Não verificação de cumprimento (nenhum parâmetro avaliado)"

    if normalize or "Sim" not in df.columns or "Não" not in df.columns:
        df_eval_grouped = (
            df.group_by(["Mês", "Parâmetro", "Valor esperado"])
            .agg(
                [
                    (pl.col("Status") == "Não").sum().alias("Não"),
                    (pl.col("Status") == "Sim").sum().alias("Sim"),
                ]
            )
            .with_columns(
                pl.struct(["Sim", "Não"])
                .map_elements(eval_mes, return_dtype=pl.Utf8)
                .alias("cumprimento")
            )
        )
    else:
        df_eval_grouped = df.with_columns(
            pl.struct(["Sim", "Não"])
            .map_elements(eval_mes, return_dtype=pl.Utf8)
            .alias("Status")
        )

    if "cumprimento" in df_eval_grouped.columns:
        df_eval_grouped = df_eval_grouped.rename({"cumprimento": "Status"})

    eval_dict: dict[str, list[str]] = {}
    for row in df_eval_grouped.iter_rows(named=True):
        cumprimento: str = row["Status"]
        mes: str = datetime.datetime.strftime(row["Mês"], "%m/%Y")
        if cumprimento not in eval_dict:
            eval_dict[cumprimento] = []
        eval_dict[cumprimento].append(mes)

    out_msg = list[str]()
    for key, val in eval_dict.items():
        msg = "* " + key + ": " + str(len(val)) + " meses -- " + ", ".join(val)
        out_msg.append(msg)

    out_msg = "\n".join(out_msg)

    return out_msg


def sat_eval_interruptions(cnpj: str, date_range: tuple[date, date]):
    interLocal = sat_get_downtimes(cnpj, date_range)

    if interLocal.is_empty():
        return (
            pl.DataFrame(),
            0,
            0,
            format_seconds(0),
            format_seconds(0),
            pl.DataFrame(),
        )
    mean_inter: float = interLocal["DIFF_HOR"].mean()  # ty: ignore[invalid-assignment]
    dev_inter: float = interLocal["DIFF_HOR"].std()  # ty: ignore[invalid-assignment]

    top10equip = interLocal.group_by(["CD_SAT", "NO_SAT"]).agg(
        [
            pl.col("DIFF_HOR").mean().alias("mean_delta"),
            pl.count("DIFF_HOR").alias("count"),
        ]
    )
    top10equip = top10equip.sort("count", descending=True).head(10)
    top10equip = top10equip.with_columns(
        pl.col("mean_delta").map_elements(
            lambda x: format_seconds(int(x * 3600)), return_dtype=pl.Utf8
        )
    )
    top10equip = top10equip.rename(
        {
            "NO_SAT": "Nome do equipamento",
            "mean_delta": "Duração média das interrupções",
            "count": "Número de interrupções",
        }
    )

    interLocal = interLocal.select(
        [
            pl.col("CD_SAT").alias("Código do equipamento"),
            pl.col("NO_SAT").alias("Nome do equipamento"),
            pl.col("DT_INSTANTE_ANTERIOR").alias("Data/hora início da interrupção"),
            pl.col("DT_INSTANTE").alias("Data/hora fim da interrupção"),
            pl.col("DT_MES").alias("Mês"),
        ]
    )

    total_inter = len(interLocal)
    equip_count: int = interLocal.select(
        pl.col("Código do equipamento").n_unique()
    ).item()
    mean_inter_str = format_seconds(int(mean_inter * 3600))
    dev_inter_str = format_seconds(int(dev_inter * 3600))

    return (
        interLocal,
        total_inter,
        equip_count,
        mean_inter_str,
        dev_inter_str,
        top10equip,
    )


class SATReporter(SubReporter):
    DATASET_NAME = "Sistema de Aquisição de Dados de Tráfego (SAT)"

    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        total_count = get_query_result(
            AVAILABLE_SAT_QUERIES["get_total_count"],
            {
                "cnpj": cnpj,
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        ).row(0)[0]
        if total_count == 0:
            return "A concessionária não apresentou nenhum dado de SAT no período selecionado."

    def build_section(
        self, section: SubReportSection, cnpj: str, date_range: tuple[date, date]
    ):
        match section:
            case SubReportSection.VISAO_GERAL:
                self.build_visao_geral(cnpj, date_range)
            case SubReportSection.PARAMETROS_OPERACIONAIS:
                self.build_parametros_operacionais(cnpj, date_range)
            case SubReportSection.ANOMALIAS:
                not_defined_msg = "No momento, não há anomalias previstas na análise desse conjunto de dados"
                self.md(not_defined_msg)
            case _:
                pass

    def build_visao_geral(self, cnpj: str, date_range: tuple[date, date]):
        _timeseries, min_date, max_date, gaps = get_gaps(cnpj, date_range)
        data_msg = "A concessionária apresentou dados completos para todos os dias do período analisado -- {periodo_inicio} a {periodo_fim}."
        if gaps:
            data_msg = "A concessionária apresentou dados **incompletos** para o período analisado ({periodo_inicio} a {periodo_fim}). Foram identificadas as seguintes lacunas."

        gaps_fmt: list[str] = []
        for gap in gaps:
            dias_fmt = "dias" if gap["length"] > 1 else "dia"
            gaps_fmt.append(
                f"* De {gap['start'].strftime('%d/%m/%Y')} a {gap['end'].strftime('%d/%m/%Y')} ({gap['length']} {dias_fmt})"
            )

        gaps_fmt_joined = "\n".join(gaps_fmt)
        data_fmt = data_msg.format(
            periodo_inicio=min_date.strftime("%d/%m/%Y"),
            periodo_fim=max_date.strftime("%d/%m/%Y"),
        )

        self.md(data_fmt)
        # plot time series of counts
        timeseries = _timeseries.set_index("DT_DIA")["QT_CONTAGEM"]
        _ = st.line_chart(
            timeseries,
            height=300,
            width="stretch",
        )
        self.append_line_chart_snapshot(timeseries)
        self.md(gaps_fmt_joined)
        total_eq = sat_get_total_equipment(cnpj, date_range)
        equip_msg = f"Foram detectados {total_eq} equipamentos ao todo. "
        failing_eq = sat_get_failing_equipment(cnpj, date_range)

        if failing_eq:
            equip_msg += (
                "Dentre estes, os seguintes equipamentos apresentaram falta de dados:\n"
            )
            for eq in failing_eq:
                equip_msg += (
                    f"\n* {eq['NO_SAT']}: {eq['QT_CONTAGEM']} registros transmitidos."
                )
        else:
            equip_msg += "Nenhum equipamento apresentou falta de dados."

        self.md(equip_msg)
        equip_map = sat_get_equipment_map(cnpj, date_range)
        self.md("#### Localização dos equipamentos")

        map_data = pd.DataFrame(
            {
                "lat": [eq["CG_LATITUDE"] for eq in equip_map],
                "lon": [eq["CG_LONGITUDE"] for eq in equip_map],
                "count": [eq["QT_CONTAGEM"] / 100 for eq in equip_map],
            }
        )
        map_data_for_download = (
            pd.DataFrame(equip_map)
            .drop(columns=["CD_SAT"])
            .rename(
                columns={
                    "NO_SAT": "Identificador",
                    "CG_LATITUDE": "Latitude",
                    "CG_LONGITUDE": "Longitude",
                    "QT_CONTAGEM": "Total de passagens",
                }
            )
            .to_csv(index=False)
            .encode("utf-8")
        )

        _ = st.map(map_data, size="QT_CONTAGEM")
        self.append_point_map_snapshot(
            map_data["lat"], map_data["lon"], map_data["count"]
        )
        _ = st.download_button(
            "Baixar tabela de coordenadas",
            data=map_data_for_download,
            file_name=f"sat_passagens_mapa_{cnpj}.csv",
            mime="text/csv",
            key=f"download_coords_sat_{cnpj}",
            icon=":material/download:",
        )

    def build_parametros_operacionais(self, cnpj: str, date_range: tuple[date, date]):
        total_eq = sat_get_total_equipment(cnpj, date_range)
        company_params, (equipment_level, system_level) = sat_get_params_description(
            cnpj
        )
        self.md(company_params)

        if equipment_level:
            params_equip = sat_eval_params_equipment_months(cnpj, date_range)
            if params_equip is None:
                self.md(
                    "Concessionária não possui nenhum parâmetro operacional definido."
                )
            else:
                self.md("#### Parâmetros a nível de equipamento")
                params_equip_display = (
                    params_equip.sort("Mês")
                    .with_columns(pl.col("Mês").dt.strftime("%m/%Y"))
                    .to_pandas()
                    .set_index(params_equip.columns[0])
                )
                self.show_table(params_equip_display)
                _ = st.download_button(
                    "Baixar tabela resumo",
                    data=params_equip_display.to_csv().encode("utf-8-sig"),
                    file_name=f"sat_resumo_parametros_equipamento_{cnpj}.csv",
                    mime="text/csv",
                    icon=":material/download:",
                    key=f"download_summary_sat_equipment_{cnpj}",
                )
                self.md(
                    "A performance da concessionária está sumarizada na relação abaixo."
                )
                performance_msg = sat_get_performance_description(params_equip, False)
                self.md(performance_msg)
        if system_level:
            params_system = sat_eval_params_system(cnpj, date_range)
            self.md("#### Parâmetros a nível de sistema")
            params_system_display = params_system.to_pandas().set_index(
                params_system.columns[0]
            )

            self.show_table(params_system_display)
            _ = st.download_button(
                "Baixar tabela resumo",
                data=params_system_display.to_csv().encode("utf-8-sig"),
                file_name=f"sat_resumo_parametros_sistema_{cnpj}.csv",
                mime="text/csv",
                icon=":material/download:",
                key=f"download_summary_sat_system_{cnpj}",
            )

            self.md(
                "A performance da concessionária está sumarizada na relação abaixo."
            )
            performance_msg = sat_get_performance_description(params_system)
            self.md(performance_msg)

        _inter, total_inter, inter_equip_count, mean_inter, dev_inter, top10equip = (
            sat_eval_interruptions(cnpj, date_range)
        )

        if total_inter == 0:
            inter_text = "**A concessionária não apresentou nenhuma interrupção registrada no período analisado.**"
        else:
            inter_text = f"""
                Ao todo, foram registradas {total_inter} interrupções no período analisado.
                Dos {total_eq} equipamentos da concessionária,
                {inter_equip_count} sofreram interrupções ao menos uma vez.
                A média de tempo de interrupção por equipamento para a concessionária foi de {mean_inter},
                com um desvio padrão de {dev_inter}.
                \n\nA tabela abaixo mostra os dez equipamentos que mais sofreram interrupções no período,
                bem como seus respectivos tempos de interrupção médios.
            """

        self.md(inter_text)

        if not top10equip.is_empty():
            top10equip_pd = (
                top10equip.drop("CD_SAT")
                .to_pandas()
                .set_index("Nome do equipamento", drop=True)
            )
            self.show_table(top10equip_pd)
            _ = st.download_button(
                "Baixar tabela completa",
                data=top10equip.to_pandas()
                .drop(columns=["CD_SAT"])
                .to_csv(index=False)
                .encode("utf-8-sig"),
                file_name=f"sat_interrupcoes_por_equipamento_{cnpj}.csv",
                mime="text/csv",
                icon=":material/download:",
                key=f"download_full_table_sat_{cnpj}",
            )
            _ = st.download_button(
                "Baixar tabela de interrupções",
                data=_inter.to_pandas().to_csv(index=False).encode("utf-8-sig"),
                file_name=f"sat_interrupcoes_{cnpj}.csv",
                mime="text/csv",
                icon=":material/download:",
                key=f"download_interruptions_sat_{cnpj}",
            )
