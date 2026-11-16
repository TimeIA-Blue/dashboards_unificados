from collections.abc import Hashable, Mapping
from datetime import date
from typing import Any, TypedDict

import pandas as pd
import streamlit as st
from numpy import uint16
from pandas._libs.tslibs.timestamps import Timestamp
from pandas.core.frame import DataFrame

from queries import get_query_result
from queries.radar import AVAILABLE_RADAR_QUERIES
from relatorio.reporter import SubReporter, SubReportSection
from spotfire import format_seconds
from spotfire.radar import radar_data_function_tables


def dataframe_to_csv(df: DataFrame) -> bytes:
    download_df = df.copy()
    for column in download_df.select_dtypes(include=["datetime", "datetimetz"]):
        download_df[column] = download_df[column].dt.strftime("%d/%m/%Y %H:%M:%S")
    for column in download_df.select_dtypes(include=["float"]):
        download_df[column] = download_df[column].round(2)
    return download_df.to_csv(index=False).encode("utf-8-sig")


class GetGapsReturnDict(TypedDict):
    group: int
    start: pd.Timestamp
    end: pd.Timestamp
    length: int


def get_gaps(
    cnpj: str, date_range: tuple[date, date]
) -> tuple[DataFrame, Timestamp, Timestamp, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_gaps"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )

    t["is_zero"] = t["count"] == 0
    t["group"] = (t["is_zero"] != t["is_zero"].shift()).cumsum()

    min_date: pd.Timestamp = t["date"].min()
    max_date: pd.Timestamp = t["date"].max()

    where_zero: DataFrame = t[t["is_zero"]]
    gaps = (
        where_zero.groupby("group")
        .agg(start=("date", "min"), end=("date", "max"), length=("date", "count"))
        .reset_index(drop=True)
    )

    # TypedDict is a mapping, dict is more strict. However, just change the way it is accessed and its fine.
    gaps_as_dicts: list[GetGapsReturnDict] = gaps.to_dict(orient="records")  # ty: ignore[invalid-assignment]

    return t, min_date, max_date, gaps_as_dicts


def get_total_equipment(cnpj: str, date_range: tuple[date, date]) -> int:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_total_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    return t["total_equipment"].iloc[0]


def get_failing_equipment(
    cnpj: str, date_range: tuple[date, date]
) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_failing_equipment"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    return t.to_dict(orient="records")


def get_equipment_map(
    cnpj: str, date_range: tuple[date, date]
) -> list[dict[Hashable, Any]]:
    t = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_equipment_map"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )
    return t.to_dict(orient="records")


radar_types = {1: "Sistema", 2: "Equipamento", 4: "Sistema (%)"}

radar_exp_formats = {
    "Equipamento": """Indisponibilidades sofridas por um equipamento não podem ultrapassar {x} horas contínuas.
    O valor esperado descrito nas tabelas é 0 (zero) pois idealmente espera-se que os equipamentos não sofram indisponibilidades.""",
    "Sistema": "A média de indisponibilidade dos elementos que compõem o sistema não pode ultrapassar {x} horas mensais.",
    "Sistema (%)": "A média percentual de disponibilidade do sistema deve ser igual ou superior a {x}%.",
}


def get_company_params(cnpj: str):
    params = get_query_result(
        AVAILABLE_RADAR_QUERIES["get_company_params"],
        {"cnpj": cnpj},
        use_polars=False,
    )

    print("PPP", params)

    params["CD_TIPO_INTERRUPCAO"] = params["CD_TIPO_INTERRUPCAO"].map(radar_types)

    out = list[str]()

    # Pyright can't infer the keys in the object
    for p in params.to_dict(orient="records"):
        value: uint16
        if p["CD_TIPO_INTERRUPCAO"] in ["Equipamento", "Sistema"]:
            value = p["VL_TEMPO_MAX_INTERRUPCAO"]
            msg = f"* **{p['CD_TIPO_INTERRUPCAO']}**: " + radar_exp_formats[
                p["CD_TIPO_INTERRUPCAO"]
            ].format(x=value)
        else:
            value = p["pct_max_interrup"]
            msg = f"* **{p['CD_TIPO_INTERRUPCAO']}**: " + radar_exp_formats[
                p["CD_TIPO_INTERRUPCAO"]
            ].format(x=value)

        out.append(msg)

    return "\n".join(out)


def eval_params(fantasia: str, date_range: tuple[date, date]) -> DataFrame:
    df_eval, _, _ = radar_data_function_tables(date_range)
    df_eval_f = df_eval[
        (df_eval["NO_FANTASIA"] == fantasia) & (df_eval["val_esp"] != "-")
    ].copy()
    df_eval_f = df_eval_f.drop(columns=["NU_CNPJ", "NO_FANTASIA", "DT_MES"])
    # month from YYYY-MM to MM/YYYY
    df_eval_f["month"] = pd.to_datetime(
        df_eval_f["DT_MES_str"], format="%Y-%m"
    ).dt.strftime("%m/%Y")
    df_eval_f = df_eval_f.rename(
        columns={
            "val_esp": "Falhas esperadas (valor máximo)",
            "month": "Mês",
            "tipo": "Parâmetro",
            "val": "Falhas contabilizadas",
            "cumpriu": "Cumprimento",
        }
    ).drop(columns=["DT_MES_str"])
    return df_eval_f


def eval_performance(df: pd.DataFrame):
    def eval_mes(row: Mapping[Hashable, Any]):
        if row["Não"] > 0 and row["Sim"] > 0:
            return "Cumprimento parcial (ao menos um parâmetro cumprido)"
        if row["Sim"] > 0:
            return "Cumprimento total (todos os parâmetros cumpridos)"
        return "Não cumprimento (todos os parâmetros descumpridos)"

    df_eval_grouped = (
        df.groupby(["Mês", "Parâmetro", "Falhas esperadas (valor máximo)"])
        .agg(
            Não=("Cumprimento", lambda x: (x == "Não").sum()),
            Sim=("Cumprimento", lambda x: (x == "Sim").sum()),
        )
        .reset_index()
    )

    df_eval_grouped["cumprimento"] = df_eval_grouped.apply(eval_mes, axis=1)

    # to dict -- index is cumprimento, values are a list of mês
    # e.g. {'Sim': ['01/2023', '02/2023'], 'Não': ['03/2023'], 'parcial': ['04/2023']}
    eval_dict: dict[str, list[str]] = {}
    for _, row in df_eval_grouped.iterrows():
        # Pyright can't infer key types
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


def eval_interruptions(cnpj: str, date_range: tuple[date, date]):
    _, _, inter = radar_data_function_tables(date_range)
    interLocal = inter[inter["NU_CNPJ"] == cnpj].copy()
    interLocal["month"] = pd.to_datetime(
        interLocal["DT_MES"], format="%Y-%m"
    ).dt.strftime("%m/%Y")
    mean_inter = interLocal["delta"].mean()
    dev_inter = interLocal["delta"].std()

    top10equip = (
        interLocal.groupby(["NO_RADAR"])
        .agg(mean_delta=("delta", "mean"), count=("delta", "count"))
        .reset_index()
    )
    top10equip = top10equip.sort_values(by="count", ascending=False)
    top10equip["mean_delta"] = top10equip["mean_delta"].apply(
        lambda x: format_seconds(int(x))
    )
    top10equip = top10equip.rename(
        columns={
            "NO_RADAR": "Nome do equipamento",
            "mean_delta": "Duração média das interrupções",
            "count": "Número de interrupções",
        }
    )

    # drop cnpj
    interLocal = interLocal.drop(
        columns=[
            "NU_CNPJ",
            "delta",
            "delta_h",
            "VL_TOLERANCIA",
            "CG_LATITUDE",
            "CG_LONGITUDE",
        ]
    )
    # put fantasia as first column in the dataframe
    interLocal = interLocal[
        ["NO_FANTASIA"] + [col for col in interLocal.columns if col != "NO_FANTASIA"]
    ]
    interLocal = interLocal.rename(
        columns={
            "CD_RADAR": "Código do equipamento",
            "NO_RADAR": "Nome do equipamento",
            "DT_INSTANTE_ANTERIOR": "Data/hora início da interrupção",
            "DT_INSTANTE": "Data/hora fim da interrupção",
            "month": "Mês",
            "NO_FANTASIA": "Concessionária",
            "delta_fmt": "Duração da interrupção",
        }
    )

    total_inter = len(interLocal)
    equip_count = interLocal["Código do equipamento"].nunique()
    mean_inter = format_seconds(int(mean_inter))
    dev_inter = format_seconds(int(dev_inter))

    return interLocal, total_inter, equip_count, mean_inter, dev_inter, top10equip


def eval_anomalies(cnpj: str, date_range: tuple[date, date]):
    _, anom, _ = radar_data_function_tables(date_range)
    anomLocal = anom[anom["NU_CNPJ"] == cnpj].copy()

    count_anom = len(anomLocal)
    count_equip = anomLocal["CD_RADAR"].nunique()
    count_mean_anom = anomLocal[anomLocal["med_anom"]]["CD_RADAR"].nunique()

    anom_fmt = anomLocal.drop(
        columns=[
            "NU_CNPJ",
            "CD_RADAR",
            "QT_CONTAGEM",
            "CG_LATITUDE",
            "CG_LONGITUDE",
            "NO_FANTASIA",
        ]
    )
    # order by month
    anom_fmt = anom_fmt.sort_values(by="DT_MES")
    anom_fmt = anom_fmt[anom_fmt["med_anom"]].drop(columns=["med_anom"])
    anom_fmt["DT_MES"] = pd.to_datetime(anom_fmt["DT_MES"], format="%Y-%m").dt.strftime(
        "%m/%Y"
    )
    anom_fmt["vel_med"] = anom_fmt["VL_VELOCIDADE_MEDIA"].round(2)
    anom_fmt["vel_med"] = anom_fmt["vel_med"].astype(str) + " km/h"
    anom_fmt["vel_min"] = anom_fmt["VL_VELOCIDADE_MINIMA"].astype(str) + " km/h"
    anom_fmt["vel_max"] = anom_fmt["VL_VELOCIDADE_MAXIMA"].astype(str) + " km/h"
    anom_fmt = anom_fmt.rename(
        columns={
            "no_radar": "Nome do equipamento",
            "DT_MES": "Mês",
            "vel_med": "Velocidade média",
            "vel_min": "Velocidade mínima",
            "vel_max": "Velocidade máxima",
            "NO_RADAR": "Radar",
        }
    ).drop(
        columns=[
            "VL_VELOCIDADE_MEDIA",
            "VL_VELOCIDADE_MINIMA",
            "VL_VELOCIDADE_MAXIMA",
            "QT_CONTAGEM_ACIMA_LIMITE",
        ]
    )
    # put Mês as first column
    anom_fmt = anom_fmt[["Mês"] + [col for col in anom_fmt.columns if col != "Mês"]]

    anomForMap = anomLocal[
        [
            "CD_RADAR",
            "NO_RADAR",
            "CG_LATITUDE",
            "CG_LONGITUDE",
            "QT_CONTAGEM",
            "med_anom",
        ]
    ].drop_duplicates()
    # if medAnom is True, color red, else yellow
    anomForMap["color"] = anomForMap["med_anom"].apply(
        lambda x: (255, 0, 0, 0.5) if x else (255, 255, 0, 0.5)
    )
    return anomForMap, anom_fmt, count_anom, count_equip, count_mean_anom


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
            _timeseries.set_index("date")["count"],
            height=300,
            width="stretch",
        )
        self.md(gaps_fmt_joined)
        self.md(equip_msg)
        equip_map = get_equipment_map(cnpj, date_range)
        self.md("#### Localização dos equipamentos")

        equipment_data = pd.DataFrame(equip_map)
        map_data = pd.DataFrame(
            {
                "lat": equipment_data["CG_LATITUDE"],
                "lon": equipment_data["CG_LONGITUDE"],
                "count": equipment_data["COUNT"] / 100,
            }
        )
        equipment_data_to_download = (
            equipment_data.drop(columns=["CD_RADAR"])
            .rename(
                columns={
                    "NO_RADAR": "Identificador",
                    "CG_LATITUDE": "Latitude",
                    "CG_LONGITUDE": "Longitude",
                    "COUNT": "Total de passagens",
                }
            )
            .to_csv(index=False)
            .encode("utf-8")
        )

        _ = st.map(map_data, size="count")
        self.append_point_map_snapshot(
            equipment_data["CG_LATITUDE"],
            equipment_data["CG_LONGITUDE"],
            equipment_data["COUNT"],
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
        company_params = get_company_params(cnpj)
        _inter, total_inter, inter_equip_count, mean_inter, dev_inter, top10equip = (
            eval_interruptions(cnpj, date_range)
        )
        _topequip = top10equip.copy()
        top10equip = top10equip.head(10)
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

        evalued_params = eval_params(company_name, date_range)

        self.show_table(evalued_params.set_index("Mês"))
        _ = st.download_button(
            "Baixar tabela resumo",
            data=dataframe_to_csv(evalued_params),
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

        pd_table = top10equip.set_index(top10equip.columns[0])
        self.show_df(pd_table)

        _ = st.download_button(
            "Baixar tabela completa",
            data=dataframe_to_csv(_topequip),
            file_name=f"radares_interrupcoes_por_equipamento_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_full_table_{cnpj}",
        )

        _ = st.download_button(
            "Baixar tabela de interrupções",
            data=dataframe_to_csv(_inter),
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
        self.show_df(anom_fmt.set_index(anom_fmt.columns[0]))
        _ = st.button(
            "Baixar tabela de aparelhos anômalos",
            icon=":material/download:",
            key=f"download_anomalous_devices_{cnpj}",
        )

        _ = self.md("""O mapa a seguir apresenta todos os aparelhos com anomalias:
            em amarelo, os aparelhos que registaram anomalias ao menos uma vez;
            em vermelho, os aparelhos que apresentam média anômala.
        """)
        map_data = anomForMap.copy()
        map_data["count"] = map_data["QT_CONTAGEM"] / 100
        _ = st.map(
            map_data,
            size="count",
            latitude="CG_LATITUDE",
            longitude="CG_LONGITUDE",
            color="color",
        )
        self.append_point_map_snapshot(
            anomForMap["CG_LATITUDE"],
            anomForMap["CG_LONGITUDE"],
            anomForMap["QT_CONTAGEM"],
            anomForMap["med_anom"],
        )
        map_details = anomForMap.drop(columns=["color"]).rename(
            columns={
                "CD_RADAR": "Código do equipamento",
                "NO_RADAR": "Nome do equipamento",
                "CG_LATITUDE": "Latitude",
                "CG_LONGITUDE": "Longitude",
                "QT_CONTAGEM": "Registros analisados",
                "med_anom": "Média anômala",
            }
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
