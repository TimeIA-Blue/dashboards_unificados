from collections.abc import Hashable, Mapping
from datetime import date
from typing import Any, TypedDict

import pandas as pd
import streamlit as st
from numpy import uint16
from pandas import DataFrame, Timestamp

from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES
from relatorio.reporter import SubReporter, SubReportSection
from spotfire.pedagio import pedagio_data_function_tables


def format_seconds(seconds: int):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}h{minutes:02d}m{secs:02d}s"


def dataframe_to_csv(df: DataFrame) -> bytes:
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
    start: pd.Timestamp
    end: pd.Timestamp
    length: int


def get_gaps(
    cnpj: str,
) -> tuple[DataFrame, Timestamp, Timestamp, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_PEDAGIO_QUERIES["get_gaps"],
        {"cnpj": cnpj},
        use_polars=False,
    )

    t["is_zero"] = t["QT_CONTAGEM"] == 0
    t["group"] = (t["is_zero"] != t["is_zero"].shift()).cumsum()

    min_date: pd.Timestamp = t["DT_DIA"].min()
    max_date: pd.Timestamp = t["DT_DIA"].max()

    where_zero: DataFrame = t[t["is_zero"]]
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


def eval_params(fantasia: str, date_range: tuple[date, date]) -> DataFrame:
    df_eval, _, _ = pedagio_data_function_tables(date_range)
    df_eval_f = df_eval[
        (df_eval["NO_FANTASIA"] == fantasia) & (df_eval["VL_VALOR_ESPERADO"] != "-")
    ].copy()
    # drop fantasia col
    df_eval_f = df_eval_f.drop(columns=["NO_FANTASIA"])
    # month from YYYY-MM to MM/YYYY
    df_eval_f["DT_MES"] = pd.to_datetime(
        df_eval_f["DT_MES"], format="%Y-%m"
    ).dt.strftime("%m/%Y")
    df_eval_f = df_eval_f.rename(
        columns={
            "VL_VALOR_ESPERADO": "Valor esperado",
            "DT_MES": "Mês",
            "tipo": "Parâmetro",
            "val": "Valor observado",
            "cumpriu": "Cumprimento",
        }
    )
    return df_eval_f


def eval_performance(df: pd.DataFrame):
    print(df)

    def eval_mes(row: Mapping[Hashable, Any]):
        if row["Não"] > 0 and row["Sim"] > 0:
            return "Cumprimento parcial (ao menos um parâmetro cumprido)"
        if row["Sim"] > 0:
            return "Cumprimento total (todos os parâmetros cumpridos)"
        return "Não cumprimento (todos os parâmetros descumpridos)"

    df_eval_grouped = (
        df.groupby(["Mês", "Parâmetro", "Valor esperado"])
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
    _, _, inter = pedagio_data_function_tables(date_range)
    interLocal = inter[inter["NU_CNPJ"] == cnpj].copy()
    interLocal["DT_MES"] = pd.to_datetime(
        interLocal["DT_MES"], format="%Y-%m"
    ).dt.strftime("%m/%Y")
    mean_inter = interLocal["VL_DELTA"].mean()
    mean_inter = 0 if pd.isna(mean_inter) else mean_inter
    dev_inter = interLocal["VL_DELTA"].std()
    dev_inter = 0 if pd.isna(dev_inter) else dev_inter

    top10equip = (
        interLocal.groupby(["NO_PRACA"])
        .agg(
            VL_DELTA_MEDIO=("VL_DELTA", "mean"),
            QT_QUANTIDADE_INTERRUP=("VL_DELTA", "count"),
        )
        .reset_index()
    )
    top10equip = top10equip.sort_values(by="QT_QUANTIDADE_INTERRUP", ascending=False)
    top10equip["VL_DELTA_MEDIO"] = top10equip["VL_DELTA_MEDIO"].apply(
        lambda x: format_seconds(int(x))
    )
    top10equip = top10equip.rename(
        columns={
            "NO_PRACA": "Nome da praça",
            "VL_DELTA_MEDIO": "Duração média das interrupções",
            "QT_QUANTIDADE_INTERRUP": "Número de interrupções",
        }
    )

    interLocal = interLocal.drop(
        columns=[
            "NU_CNPJ",
            "VL_DELTA",
            "VL_DELTA_HORA",
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
            "CD_PRACA": "Código da praça",
            "NO_PRACA": "Nome da praça",
            "DT_INSTANTE_ANTERIOR": "Data/hora início da interrupção",
            "DT_INSTANTE": "Data/hora fim da interrupção",
            "DT_MES": "Mês",
            "NO_FANTASIA": "Concessionária",
            "DS_DELTA_FORMATADO": "Duração da interrupção",
        }
    )

    total_inter = len(interLocal)
    equip_count = interLocal["Código da praça"].nunique()
    mean_inter = format_seconds(int(mean_inter))
    dev_inter = format_seconds(int(dev_inter))

    return interLocal, total_inter, equip_count, mean_inter, dev_inter, top10equip


def eval_anomalies(cnpj: str, date_range: tuple[date, date]):
    _, anom, _ = pedagio_data_function_tables(date_range)
    anomLocal = anom[anom["NU_CNPJ"] == cnpj].copy()

    # mean of p_evasao per cd_praca
    anomMean = (
        anomLocal.groupby("CD_PRACA")
        .agg(mean_p_evasao=("VL_PCT_EVASOES", "mean"))
        .reset_index()
    )
    qtd_high = anomMean[anomMean["mean_p_evasao"] >= 0.1]
    qtd_medium = anomMean[
        (anomMean["mean_p_evasao"] >= 0.05) & (anomMean["mean_p_evasao"] < 0.1)
    ]
    qtd_low = anomMean[
        (anomMean["mean_p_evasao"] >= 0.01) & (anomMean["mean_p_evasao"] < 0.05)
    ]
    qtd_very_low = anomMean[anomMean["mean_p_evasao"] < 0.01]
    qtds = (len(qtd_high), len(qtd_medium), len(qtd_low), len(qtd_very_low))

    total_evasions = anomLocal["QT_TOTAL_EVASOES"].sum()

    # group by cd_praca, lat, lon, get mean of evasoes
    anomMap = (
        anomLocal.groupby(["CD_PRACA", "NO_PRACA", "CG_LATITUDE", "CG_LONGITUDE"])
        .agg(count=("QT_TOTAL_EVASOES", "mean"))
        .reset_index()
    )
    # merge with anomMean to get mean_p_evasao
    anomMap = anomMap.merge(anomMean, on="CD_PRACA")
    anomMap["color"] = anomMap["mean_p_evasao"].apply(
        lambda x: (
            "#e63131"
            if x >= 0.1
            else "#e6b800"
            if x >= 0.05
            else "#00cc00"
            if x >= 0.01
            else "#0066ff"
        )
    )

    print("--- mapa ---")
    print(anomMap)
    print("------")

    # group by cd_praca, month, get mean of p_evasao
    anomPctMonth = (
        anomLocal.groupby(["CD_PRACA", "NO_PRACA", "DT_MES"])
        .agg(p_evasao=("VL_PCT_EVASOES", "mean"))
        .reset_index()
    )

    return total_evasions, qtds, anomMap, anomPctMonth


class PedagioReporter(SubReporter):
    DATASET_NAME = "Sistema de pedágios"

    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        total_count = get_query_result(
            AVAILABLE_PEDAGIO_QUERIES["get_total_count"],
            {
                "cnpj": cnpj,
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        ).row(0)[0]
        if total_count == 0:
            return "A concessionária não apresentou nenhum dado de Pedágios no período selecionado."

    def build_section(
        self, section: SubReportSection, cnpj: str, date_range: tuple[date, date]
    ):
        total_eq = get_total_equipment(cnpj)
        match section:
            case SubReportSection.VISAO_GERAL:
                self.build_visao_geral(cnpj, total_eq, date_range)
            case SubReportSection.PARAMETROS_OPERACIONAIS:
                self.build_parametros_operacionais(cnpj, total_eq, date_range)
            case SubReportSection.ANOMALIAS:
                self.build_anomalias(cnpj, total_eq, date_range)
            case _:
                pass

    def build_visao_geral(
        self, cnpj: str, total_eq: int, date_range: tuple[date, date]
    ):
        _timeseries, min_date, max_date, gaps = get_gaps(cnpj)
        company_name: str = self.company_name(cnpj)
        _inter, total_inter, inter_equip_count, mean_inter, dev_inter, top10equip = (
            eval_interruptions(cnpj, date_range)
        )
        equip_msg = f"Foram detectadas {total_eq} praças ao todo. "
        failing_eq = get_failing_equipment(cnpj)
        if total_eq == inter_equip_count:
            inter_equip_count = "todos"

        if failing_eq:
            equip_msg += (
                "Dentre estes, as seguintes praças apresentaram falta de dados:"
            )
            for eq in failing_eq:
                equip_msg += (
                    f"\n* {eq['NO_PRACA']}: {eq['QT_CONTAGEM']} registros transmitidos."
                )
        else:
            equip_msg += "Nenhuma praça apresentou falta de dados."

        self.md(f"### {company_name}")

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
        _ = st.line_chart(
            _timeseries.set_index("DT_DIA")["QT_CONTAGEM"],
            height=300,
            width="stretch",
        )
        self.md(gaps_fmt_joined)
        self.md(equip_msg)
        equip_map = get_equipment_map(cnpj)
        self.md("#### Localização das praças de pedágio")

        map_data = pd.DataFrame(
            {
                "lat": [eq["CG_LATITUDE"] for eq in equip_map],
                "lon": [eq["CG_LONGITUDE"] for eq in equip_map],
                "QT_CONTAGEM": [(eq["QT_CONTAGEM"]) for eq in equip_map],
            }
        )
        map_data["QT_CONTAGEM"] /= map_data["QT_CONTAGEM"].sum()
        map_data["QT_CONTAGEM"] *= 100_000

        _ = st.map(map_data, size="QT_CONTAGEM")
        self.append_point_map_snapshot(
            map_data["lat"], map_data["lon"], map_data["QT_CONTAGEM"]
        )
        _ = st.button(
            "Baixar tabela de coordenadas",
            icon=":material/download:",
            key=f"download_pedagio_coords_{cnpj}",
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

        self.md("#### Avaliação dos parâmetros operacionais")

        msg = f"""
            Para a concessionária {company_name},
            foram estabelecidos pelo Programa de Exploração a Rodovia (PER)
            os seguintes parâmetros operacionais para o sistema de pedágios.
            """
        self.md(msg)
        self.md(company_params)

        evalued_params = eval_params(company_name, date_range)
        if not evalued_params.empty:
            self.show_table(evalued_params.set_index(evalued_params.columns[0]))
            _ = st.button(
                "Baixar tabela resumo",
                icon=":material/download:",
                key=f"download_pedagio_summary_{cnpj}",
            )

            self.md(
                "A performance da concessionária está sumarizada na relação abaixo."
            )
            performance_msg = eval_performance(evalued_params)
            self.md(performance_msg)
        msg = f"""
                Ao todo, foram registradas {total_inter} interrupções no período analisado.
                Das {total_eq} praças da concessionária,
                {inter_equip_count} sofreram interrupções ao menos uma vez.
                A média de tempo de interrupção por praça para a concessionária foi de {mean_inter},
                com um desvio padrão de {dev_inter}.
                \n\nA tabela abaixo mostra as dez praças que mais sofreram interrupções no período,
                bem como seus respectivos tempos de interrupção médios.
            """
        self.md(msg)

        self.show_table(top10equip.set_index(top10equip.columns[0]))
        _ = st.download_button(
            "Baixar tabela completa",
            data=dataframe_to_csv(_topequip),
            file_name=f"pedagios_interrupcoes_por_praca_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_pedagio_full_table_{cnpj}",
        )

        _ = st.download_button(
            "Baixar tabela de interrupções",
            data=dataframe_to_csv(_inter),
            file_name=f"pedagios_interrupcoes_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_pedagio_interruptions_{cnpj}",
        )

    def build_anomalias(self, cnpj: str, total_eq: int, date_range: tuple[date, date]):
        total_evasions, qtds, evasoesMap, evasoesMonth = eval_anomalies(
            cnpj, date_range
        )
        count_anom_high, count_anom_mean, count_anom_low, count_praca_no_anom = qtds

        evasoesMonthMean = (
            evasoesMonth.groupby(["CD_PRACA", "NO_PRACA"])
            .agg(mean_p_evasao=("p_evasao", "mean"))
            .reset_index()
        )
        evasoesMonthMean["mean_p_evasao"] = evasoesMonthMean["mean_p_evasao"].apply(
            lambda x: f"{x * 100:.2f}%"
        )
        evasoesMonthMean["categoria"] = evasoesMonthMean["mean_p_evasao"].apply(
            lambda x: (
                "Alta"
                if float(x[:-1]) >= 10
                else "Média"
                if float(x[:-1]) >= 5
                else "Baixa"
                if float(x[:-1]) >= 1
                else "Muito baixa"
            )
        )

        self.md("#### Evasões por praça de pedágio")
        msg = f"""
            Foram encontradas {total_evasions} ocorrências de evasões dentre os registros analisados.
            A determinação de uma evasão se dá internamente pelo SIR, não cabendo a este assistente nenhuma análise adicional sobre a metodologia adotada.
                    
            Das {total_eq} praças de pedágio da concessionária:
            * {count_anom_high} praças apresentaram taxa média de evasões alta;
            * {count_anom_mean} praças apresentaram taxa média de evasões média;
            * {count_anom_low} praças apresentaram taxa média de evasões baixa;
            * {count_praca_no_anom} praças apresentaram taxa média de evasões muito baixa.

            A seguir, é apresentada a tabela com o detalhamento da proporção média de evasões por praça de pedágio.
            A tabela pode ser baixada em sua versão resumida, ou detalhada mensalmente.
        """
        self.md(msg)

        pd_table = evasoesMonthMean.rename(
            columns={
                "CD_PRACA": "Código da praça",
                "NO_PRACA": "Nome da praça",
                "mean_p_evasao": "Porcentagem média de evasões",
                "categoria": "Classificação",
            }
        ).set_index("Código da praça")
        self.show_table(pd_table)

        _ = st.button(
            "Baixar tabela resumida",
            icon=":material/download:",
            key=f"download_pedagio_evasoes_summary_{cnpj}",
        )
        _ = st.button(
            "Baixar tabela detalhada",
            icon=":material/download:",
            key=f"download_pedagio_evasoes_detailed_{cnpj}",
        )

        msg = """
        A seguir estão mapeadas todas as praças por categoria de evasão, seguindo a codificação:

        * Alta (> 10%): :red[vermeho];
        * Média [5-10%): :yellow[amarelo];
        * Baixa [1-5%): :green[verde];
        * Muito baixa (< 1%): :blue[azul].
        """
        self.md(msg)

        if evasoesMap["count"].mean() < 1000:
            evasoesMap["count"] = evasoesMap["count"] * 10
        else:
            evasoesMap["count"] = evasoesMap["count"] / 10

        evasoesMap["CG_LATITUDE"] = evasoesMap["CG_LATITUDE"].astype(float)
        evasoesMap["CG_LONGITUDE"] = evasoesMap["CG_LONGITUDE"].astype(float)
        _ = st.map(
            evasoesMap,
            size="count",
            color="color",
            latitude="CG_LATITUDE",
            longitude="CG_LONGITUDE",
        )
        self.append_point_map_snapshot(
            evasoesMap["CG_LATITUDE"],
            evasoesMap["CG_LONGITUDE"],
            evasoesMap["count"],
            evasoesMap["color"],
        )
