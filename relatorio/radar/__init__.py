from datetime import date, datetime
from typing import Any, TypedDict

import polars as pl
import streamlit as st
from numpy import uint16
from pandas.core.frame import DataFrame

from queries import get_query_result
from queries.radar import AVAILABLE_RADAR_QUERIES
from relatorio.radar.anomalies import eval_anomalies
from relatorio.radar.helpers import DS_TIPO_BY_CODE
from relatorio.radar.interruptions import eval_interruptions
from relatorio.radar.params import eval_params
from relatorio.reporter import SubReporter, SubReportSection


def dataframe_to_csv(df: DataFrame) -> bytes:
    download_df = df.copy()
    for column in download_df.select_dtypes(include=["datetime", "datetimetz"]):
        download_df[column] = download_df[column].dt.strftime("%d/%m/%Y %H:%M:%S")
    for column in download_df.select_dtypes(include=["float"]):
        download_df[column] = download_df[column].round(2)
    return download_df.to_csv(index=False).encode("utf-8-sig")


class GetGapsReturnDict(TypedDict):
    group: int
    start: date | datetime
    end: date | datetime
    length: int


def get_gaps(
    cnpj: str, date_range: tuple[date, date]
) -> tuple[pl.DataFrame, date, date, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_gaps"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )

    t = t.with_columns(
        [
            pl.col("count").eq(0).alias("is_zero"),
        ]
    ).with_columns(
        pl.col("is_zero")
        .ne(pl.col("is_zero").shift())
        .fill_null(True)
        .cum_sum()
        .alias("group")
    )

    min_date = t["date"].min()
    max_date = t["date"].max()
    if not isinstance(min_date, date) or not isinstance(max_date, date):
        raise TypeError("Radar gap dates must be date values")

    where_zero = t.filter(pl.col("is_zero"))
    gaps = where_zero.group_by("group").agg(
        [
            pl.col("date").min().alias("start"),
            pl.col("date").max().alias("end"),
            pl.col("date").count().alias("length"),
        ]
    )

    gaps_as_dicts: list[GetGapsReturnDict] = gaps.to_dicts()  # ty: ignore[invalid-assignment]

    return t, min_date, max_date, gaps_as_dicts


def get_total_equipment(cnpj: str, date_range: tuple[date, date]) -> int:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_total_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )
    return t["total_equipment"][0]


def get_failing_equipment(
    cnpj: str, date_range: tuple[date, date]
) -> list[dict[str, Any]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_failing_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )
    return t.to_dicts()


def get_equipment_map(cnpj: str, date_range: tuple[date, date]) -> list[dict[str, Any]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_equipment_map"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )
    return t.to_dicts()


radar_exp_formats = {
    "Equipamento": """Indisponibilidades sofridas por um equipamento não podem ultrapassar {x} horas contínuas.
    O valor esperado descrito nas tabelas é 0 (zero) pois idealmente espera-se que os equipamentos não sofram indisponibilidades.""",
    "Sistema": "A média de indisponibilidade dos elementos que compõem o sistema não pode ultrapassar {x} horas mensais.",
    "Sistema (%)": "A média percentual de disponibilidade do sistema deve ser igual ou superior a {x}%.",
}


def format_params_message(cnpj: str):
    params = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=True,
    )

    params = params.with_columns(
        pl.col("CD_TIPO_INTERRUPCAO")
        .map_elements(lambda x: DS_TIPO_BY_CODE.get(x, []))
        .alias("PARTES_PARAMETRO")
    )

    out = list[str]()
    for p in params.to_dicts():
        value: uint16
        if "Equipamento" in p["PARTES_PARAMETRO"]:
            value = p["VL_TEMPO_MAX_INTERRUPCAO"]
            msg = (
                f"* **Equipamento**: {radar_exp_formats['Equipamento'].format(x=value)}"
            )
            out.append(msg)
        if "Sistema" in p["PARTES_PARAMETRO"]:
            value = p["VL_TEMPO_MAX_INTERRUPCAO"]
            msg = f"* **Sistema**: {radar_exp_formats['Sistema'].format(x=value)}"
            out.append(msg)
        if "Sistema (%)" in p["PARTES_PARAMETRO"]:
            value = p["VL_PCT_MAX_INTERRUPCAO"]
            msg = (
                f"* **Sistema (%)**: {radar_exp_formats['Sistema (%)'].format(x=value)}"
            )
            out.append(msg)

    return "\n".join(out)


def eval_performance(df: pl.DataFrame):
    eval_mes_expr = (
        pl.when((pl.col("Não") > 0) & (pl.col("Sim") > 0))
        .then(pl.lit("Cumprimento parcial (ao menos um parâmetro cumprido)"))
        .when(pl.col("Sim") > 0)
        .then(pl.lit("Cumprimento total (todos os parâmetros cumpridos)"))
        .otherwise(pl.lit("Não cumprimento (todos os parâmetros descumpridos)"))
    )

    df_eval_grouped = df.group_by(
        ["Mês", "Parâmetro", "Falhas esperadas (valor máximo)"]
    ).agg(
        [
            pl.col("Cumprimento")
            .filter(pl.col("Cumprimento") == "Sim")
            .count()
            .alias("Sim"),
            pl.col("Cumprimento")
            .filter(pl.col("Cumprimento") == "Não")
            .count()
            .alias("Não"),
        ]
    )

    df_eval_grouped = df_eval_grouped.with_columns(eval_mes_expr.alias("cumprimento"))

    # to dict -- index is cumprimento, values are a list of mês
    # e.g. {'Sim': ['01/2023', '02/2023'], 'Não': ['03/2023'], 'parcial': ['04/2023']}
    eval_dict: dict[str, list[str]] = {}
    for row in df_eval_grouped.iter_rows(named=True):
        cumprimento: str = row["cumprimento"]
        mes: str = row["Mês"]
        if cumprimento not in eval_dict:
            eval_dict[cumprimento] = []
        eval_dict[cumprimento].append(mes)

    out_msg = list[str]()
    for key, val in eval_dict.items():
        msg = "* " + key + ": " + str(len(val)) + " meses -- " + ", ".join(val)
        out_msg.append(msg)

    out_msg = "\n".join(out_msg)

    return out_msg


class RadarReporter(SubReporter):
    DATASET_NAME = "Radar"

    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        total_count = get_query_result(
            AVAILABLE_RADAR_QUERIES["get_total_count"],
            {
                "cnpj": cnpj,
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        ).row(0)[0]
        if total_count == 0:
            return "A concessionária não apresentou nenhum dado de Radar no período selecionado."

    def build_section(
        self, section: SubReportSection, cnpj: str, date_range: tuple[date, date]
    ):
        total_eq = get_total_equipment(cnpj, date_range)
        match section:
            case SubReportSection.VISAO_GERAL:
                self.build_visao_geral(cnpj, date_range, total_eq)
            case SubReportSection.PARAMETROS_OPERACIONAIS:
                self.build_parametros_operacionais(cnpj, total_eq, date_range)
            case SubReportSection.ANOMALIAS:
                self.build_anomalias(cnpj, date_range, total_eq)
            case _:
                pass

    def build_visao_geral(
        self, cnpj: str, date_range: tuple[date, date], total_eq: int
    ):
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

        equip_msg = f"Foram detectados {total_eq} equipamentos ao todo. "
        failing_eq = get_failing_equipment(cnpj, date_range)

        if failing_eq:
            equip_msg += (
                "Dentre estes, os seguintes equipamentos apresentaram falta de dados:"
            )
            for eq in failing_eq:
                equip_msg += (
                    f"\n* {eq['NO_RADAR']}: {eq['count']} registros transmitidos."
                )
        else:
            equip_msg += "Nenhum equipamento apresentou falta de dados."
        gaps_fmt_joined = "\n".join(gaps_fmt)
        data_fmt = data_msg.format(
            periodo_inicio=min_date.strftime("%d/%m/%Y"),
            periodo_fim=max_date.strftime("%d/%m/%Y"),
        )
        self.md(data_fmt)
        _ = st.line_chart(
            _timeseries.to_pandas().set_index("date")["count"],
            height=300,
            width="stretch",
        )
        self.md(gaps_fmt_joined)
        self.md(equip_msg)
        equip_map = get_equipment_map(cnpj, date_range)
        self.md("#### Localização dos equipamentos")

        equipment_data = pl.DataFrame(equip_map)
        equipment_data_pd = equipment_data.to_pandas()
        map_data = equipment_data.select(
            [
                pl.col("CG_LATITUDE").alias("lat"),
                pl.col("CG_LONGITUDE").alias("lon"),
                (pl.col("COUNT") / 100).alias("count"),
            ]
        ).to_pandas()
        equipment_data_to_download = (
            equipment_data.drop("CD_RADAR")
            .rename(
                {
                    "NO_RADAR": "Identificador",
                    "CG_LATITUDE": "Latitude",
                    "CG_LONGITUDE": "Longitude",
                    "COUNT": "Total de passagens",
                }
            )
            .to_pandas()
            .to_csv(index=False)
            .encode("utf-8")
        )

        _ = st.map(map_data, size="count")
        self.append_point_map_snapshot(
            equipment_data_pd["CG_LATITUDE"],
            equipment_data_pd["CG_LONGITUDE"],
            equipment_data_pd["COUNT"],
        )

        _ = st.download_button(
            "Baixar tabela de coordenadas",
            data=equipment_data_to_download,
            file_name=f"radares_coordenadas_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_coords_{cnpj}",
        )

    def build_parametros_operacionais(
        self, cnpj: str, total_eq: int, date_range: tuple[date, date]
    ):
        company_name = self.company_name(cnpj)
        company_params = format_params_message(cnpj)
        inter, total_inter, inter_equip_count, mean_inter, dev_inter, top_equips = (
            eval_interruptions(cnpj, date_range)
        )
        top10equip = top_equips.head(10)
        if total_eq == inter_equip_count:
            inter_equip_count = "todos"
        self.md("#### Avaliação dos parâmetros operacionais")
        msg = f"""
            Para a concessionária {company_name},
            foram estabelecidos pelo Programa de Exploração a Rodovia (PER)
            os seguintes parâmetros operacionais para o sistema de controle de velocidade.
            """
        self.md(msg)
        self.md(company_params)

        evalued_params = eval_params(cnpj, date_range)

        eval_params_pd = evalued_params.to_pandas()
        self.show_table(eval_params_pd.set_index("Mês"))
        _ = st.download_button(
            "Baixar tabela resumo",
            data=dataframe_to_csv(eval_params_pd),
            file_name=f"radares_resumo_parametros_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_summary_{cnpj}",
        )

        self.md("A performance da concessionária está sumarizada na relação abaixo.")
        performance_msg = eval_performance(evalued_params)
        self.md(performance_msg)
        msg = f"""
                Ao todo, foram registradas {total_inter} interrupções no período analisado.
                Dos {total_eq} equipamentos da concessionária,
                {inter_equip_count} sofreram interrupções ao menos uma vez.
                A média de tempo de interrupção por equipamento para a concessionária foi de {mean_inter},
                com um desvio padrão de {dev_inter}.
                \n\nA tabela abaixo mostra os dez equipamentos que mais sofreram interrupções no período,
                bem como seus respectivos tempos de interrupção médios.
            """
        self.md(msg)

        top10equip_pd = top10equip.to_pandas()
        self.show_df(top10equip_pd.set_index(top10equip.columns[0]))

        _ = st.download_button(
            "Baixar tabela completa",
            data=dataframe_to_csv(top10equip_pd),
            file_name=f"radares_interrupcoes_por_equipamento_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_full_table_{cnpj}",
        )

        _ = st.download_button(
            "Baixar tabela de interrupções",
            data=dataframe_to_csv(inter.to_pandas()),
            file_name=f"radares_interrupcoes_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_interruptions_{cnpj}",
        )

    def build_anomalias(self, cnpj: str, date_range: tuple[date, date], total_eq: int):
        anomForMap, anom_fmt, count_anom, count_equip_anom, count_mean_anom = (
            eval_anomalies(cnpj, date_range)
        )

        self.md(f"""
            #### Anomalias nas velocidades
                    
            Foram encontradas {count_anom} ocorrências de velocidades anômalas dentre os registros analisados. São consideras anômalas velocidades:
                    
            * Inferiores a **20 km/h**;
            * Superiores a **200 km/h**.
                    
            Dos {total_eq} equipamentos monitorados
            * {count_equip_anom} apresentaram ao menos uma ocorrência de velocidade anômala.
            * {count_mean_anom} apresentaram média de velocidade fora dos limites aceitáveis, dispostos na tabela abaixo.
        """)
        anom_fmt_pd = anom_fmt.to_pandas()
        self.show_df(anom_fmt_pd.set_index(anom_fmt.columns[0]))
        _ = st.download_button(
            "Baixar tabela de aparelhos anômalos",
            data=dataframe_to_csv(anom_fmt_pd),
            file_name=f"radares_aparelhos_anomalos_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_anomalous_devices_{cnpj}",
        )

        _ = self.md("""O mapa a seguir apresenta todos os aparelhos com anomalias:
            em amarelo, os aparelhos que registaram anomalias ao menos uma vez;
            em vermelho, os aparelhos que apresentam média anômala.
        """)
        map_data = anomForMap.to_pandas().copy()
        map_data["count"] = map_data["QT_CONTAGEM"] / 100
        map_data["color"] = [(r, g, b, a) for (r, g, b, a) in map_data["color"]]
        _ = st.map(
            map_data,
            size="count",
            latitude="CG_LATITUDE",
            longitude="CG_LONGITUDE",
            color="color",
        )
        anomForMapPD = anomForMap.to_pandas()
        self.append_point_map_snapshot(
            anomForMapPD["CG_LATITUDE"],
            anomForMapPD["CG_LONGITUDE"],
            anomForMapPD["QT_CONTAGEM"],
            anomForMapPD["med_anom"],
        )
        map_details = (
            anomForMap.to_pandas()
            .drop(columns=["color"])
            .rename(
                columns={
                    "CD_RADAR": "Código do equipamento",
                    "NO_RADAR": "Nome do equipamento",
                    "CG_LATITUDE": "Latitude",
                    "CG_LONGITUDE": "Longitude",
                    "QT_CONTAGEM": "Registros analisados",
                    "med_anom": "Média anômala",
                }
            )
        )
        map_details["Média anômala"] = map_details["Média anômala"].map(
            {True: "Sim", False: "Não"}
        )
        _ = st.download_button(
            "Baixar detalhes do mapa",
            data=dataframe_to_csv(map_details),
            file_name=f"radares_detalhes_anomalias_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_map_details_{cnpj}",
        )
