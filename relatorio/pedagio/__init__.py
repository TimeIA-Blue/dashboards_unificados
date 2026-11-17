from datetime import date

import pandas as pd
import polars as pl
import streamlit as st

from queries import get_query_result
from queries.pedagio import AVAILABLE_PEDAGIO_QUERIES
from relatorio.pedagio.anomalies import eval_anomalies
from relatorio.pedagio.helpers import (
    dataframe_to_csv,
    get_company_params,
    get_equipment_map,
    get_failing_equipment,
    get_gaps,
    get_total_equipment,
)
from relatorio.pedagio.interruptions import eval_interruptions
from relatorio.pedagio.params import eval_params
from relatorio.reporter import SubReporter, SubReportSection


def eval_performance(df: pl.DataFrame):
    df_eval_grouped = df.group_by(["Mês", "Parâmetro", "Valor esperado"]).agg(
        pl.col("Cumprimento").eq("Não").sum().alias("Não"),
        pl.col("Cumprimento").eq("Sim").sum().alias("Sim"),
    )
    df_eval_grouped = df_eval_grouped.with_columns(
        pl.when([pl.col("Não") > 0, pl.col("Sim") > 0])
        .then("Cumprimento parcial (ao menos um parâmetro cumprido)")
        .when(pl.col("Sim") > 0)
        .then("Cumprimento total (todos os parâmetros cumpridos)")
        .otherwise("Não cumprimento (todos os parâmetros descumpridos)")
    )

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
        (
            _inter,
            _total_inter,
            inter_equip_count,
            _mean_inter,
            _dev_inter,
            _top_equips,
        ) = eval_interruptions(cnpj, date_range)
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
        _inter, total_inter, inter_equip_count, mean_inter, dev_inter, top_equips = (
            eval_interruptions(cnpj, date_range)
        )
        top_10_equips = top_equips.head(10).to_pandas()

        self.md("#### Avaliação dos parâmetros operacionais")

        msg = f"""
            Para a concessionária {company_name},
            foram estabelecidos pelo Programa de Exploração a Rodovia (PER)
            os seguintes parâmetros operacionais para o sistema de pedágios.
            """
        self.md(msg)
        self.md(company_params)

        evalued_params = eval_params(cnpj, date_range)
        if not evalued_params.is_empty():
            data_to_table = evalued_params.to_pandas().set_index(
                evalued_params.columns[0]
            )
            self.show_table(data_to_table)
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

        self.show_table(top_10_equips.set_index(top_10_equips.columns[0]))
        _ = st.download_button(
            "Baixar tabela completa",
            data=dataframe_to_csv(top_equips.to_pandas()),
            file_name=f"pedagios_interrupcoes_por_praca_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_pedagio_full_table_{cnpj}",
        )

        _ = st.download_button(
            "Baixar tabela de interrupções",
            data=dataframe_to_csv(_inter.to_pandas()),
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

        evasoesMonthMean = evasoesMonth.group_by(["CD_PRACA", "NO_PRACA"]).agg(
            pl.col("p_evasao").mean().alias("mean_p_evasao")
        )
        evasoesMonthMean = evasoesMonthMean.with_columns(
            pl.when(pl.col("mean_p_evasao") >= 0.1)
            .then(pl.lit("Alta"))
            .when(pl.col("mean_p_evasao") >= 0.05)
            .then(pl.lit("Média"))
            .when(pl.col("mean_p_evasao") >= 0.01)
            .then(pl.lit("Baixa"))
            .otherwise(pl.lit("Muito baixa"))
            .alias("categoria")
        )
        evasoesMonthMean = evasoesMonthMean.with_columns(
            pl.format("{}%", pl.col("mean_p_evasao").mul(100).round(2)).alias(
                "mean_p_evasao"
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

        pd_table = (
            evasoesMonthMean.rename(
                {
                    "CD_PRACA": "Código da praça",
                    "NO_PRACA": "Nome da praça",
                    "mean_p_evasao": "Porcentagem média de evasões",
                    "categoria": "Classificação",
                }
            )
            .to_pandas()
            .set_index("Código da praça")
        )
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

        * Alta (> 10%): <span style="color: red;">vermelho</span>;
        * Média [5-10%): <span style="color: #f1c40f;">amarelo</span>;
        * Baixa [1-5%): <span style="color: green;">verde</span>;
        * Muito baixa (< 1%): <span style="color: blue;">azul</span>.
        """
        self.md(msg)

        if evasoesMap["count"].mean() < 1000:
            evasoesMap = evasoesMap.with_columns(pl.col("count").mul(10))
        else:
            evasoesMap = evasoesMap.with_columns(pl.col("count").truediv(100))
        evasoesMap = evasoesMap.to_pandas()

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
