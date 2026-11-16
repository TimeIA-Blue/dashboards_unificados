from datetime import date

import streamlit as st

from queries import get_query_result
from queries.vit import (
    AVAILABLE_VIT_QUERIES,
    get_company_eval,
    get_daily_data,
    get_registered_vehicles,
    get_vehicle_counts,
    get_vit_points,
)
from relatorio.reporter import SubReporter, SubReportSection

vit_eval_msg = {
    "none": "Não cumprimento (todos os parâmetros descumpridos)",
    "all": "Cumprimento total (todos os parâmetros cumpridos)",
    "partial": "Cumprimento parcial (alguns parâmetros cumpridos)",
}


class VITReporter(SubReporter):
    DATASET_NAME = "Sistema de Veículos de Inspeção de Tráfego (VIT)"

    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        total_count = get_query_result(
            AVAILABLE_VIT_QUERIES["get_total_count"],
            {
                "cnpj": cnpj,
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        ).row(0)[0]
        if total_count == 0:
            return "A concessionária não apresentou nenhum avistamento de VIT no período selecionado."

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
        company_name = self.company_name(cnpj)
        qtd_vit_min, qtd_vit_cadastro, qtd_vit_avistados = get_vehicle_counts(cnpj)
        start_date_human = date_range[0].strftime("%d/%m/%Y")
        end_date_human = date_range[1].strftime("%d/%m/%Y")
        start_date = date_range[0].strftime("%Y-%m-%d")
        end_date = date_range[1].strftime("%Y-%m-%d")

        msg_1 = f"""
        A concessionária apresenta avistamentos de Veículos de Inspeção de Tráfego (VIT) entre os dias {start_date_human} e {end_date_human}.

        Está estabelecido no PER da concessionária {company_name} que a mesma deve possuir no mínimo
        **{qtd_vit_min}** Veículos de Inspeção de Tráfego (VIT) operando em sua malha rodoviária.

        Na relação de recursos operacionais enviada à agência, a concessionária informou a
        existência de **{qtd_vit_cadastro}** viaturas, dentre as que operam primariamente ou secundariamente como veículos de inspeção de tráfego.

        Destes {qtd_vit_cadastro}, foram encontrados **{qtd_vit_avistados}** veículos em operação nos registros de
        pontos (radares e pedágios) pertencentes à concessionária no período de análise.

        A seguir estão dispostas uma série temporal de avistamentos diários de VITs, bem como a
        relação de veículos cadastrados, enviada pela concessionária.
        """

        self.md(msg_1)
        self._current_report_html.append(f"<p>{msg_1}</p>")

        vit_daily_data = get_daily_data(cnpj, start_date, end_date)

        _ = st.line_chart(
            vit_daily_data.set_index("DT_DIA")["QT_CONTAGEM"],
            height=300,
            width="stretch",
        )

        vehicles_table = get_registered_vehicles(cnpj)
        vehicles_table = vehicles_table.rename(
            columns={
                "DS_IDENTIFICADOR": "ID do veículo",
                "DS_PLACA": "Placa",
                "DS_TIPO_VEICULO": "Tipo do veículo",
                "DS_SERVICO_PRIMARIO": "Serviço principal",
            }
        )
        self.show_table(vehicles_table.set_index(vehicles_table.columns[0]))

        _ = st.download_button(
            "Baixar relação de veículos cadastrados",
            data=vehicles_table.to_csv(index=False).encode("utf-8"),
            file_name=f"vit_veiculos_cadastrados_{cnpj}.csv",
            mime="text/csv",
            key=f"download_vit_vehicles_{cnpj}",
            icon=":material/download:",
        )

        msg_2 = """
        Para detectar avistamentos de VIT, foram utilizados os pontos a seguir, dentre radadres (em :blue[azul]) e pedágios (em :orange[laranja]).
        """

        vit_points = get_vit_points(cnpj, date_range)
        vit_points["color"] = vit_points["DS_TIPO_PONTO"].apply(
            lambda x: "#0000FF" if x == "Radar" else "#FFA500"
        )
        vit_points_map = vit_points[
            ["CG_LATITUDE", "CG_LONGITUDE", "QT_CONTAGEM", "color"]
        ].copy()
        vit_points_map["QT_CONTAGEM"] = vit_points_map["QT_CONTAGEM"]
        vit_points_df = vit_points[["NO_PONTO", "DS_TIPO_PONTO", "QT_CONTAGEM"]].rename(
            columns={
                "NO_PONTO": "Nome do ponto",
                "DS_TIPO_PONTO": "Tipo do ponto",
                "QT_CONTAGEM": "Número de avistamentos",
            }
        )
        self.md(msg_2)
        self._current_report_html.append(f"<p>{msg_2}</p>")
        _ = st.map(
            vit_points_map,
            latitude="CG_LATITUDE",
            longitude="CG_LONGITUDE",
            size="QT_CONTAGEM",
            color="color",
        )
        self.append_point_map_snapshot(
            vit_points_map["CG_LATITUDE"],
            vit_points_map["CG_LONGITUDE"],
            vit_points_map["QT_CONTAGEM"],
            vit_points_map["color"],
        )
        self.show_table(vit_points_df.set_index("Nome do ponto"))

        _ = st.download_button(
            "Baixar relação de pontos de avistamento de VIT",
            data=vit_points_df.to_csv(index=False).encode("utf-8"),
            file_name=f"vit_pontos_observacao_{cnpj}.csv",
            mime="text/csv",
            key=f"download_vit_points_{cnpj}",
            icon=":material/download:",
        )

    def build_parametros_operacionais(self, cnpj: str, date_range: tuple[date, date]):
        company_name = self.company_name(cnpj)
        self.md("#### Avaliação dos parâmetros operacionais")
        self._current_report_html.append(
            "<h4>Avaliação dos parâmetros operacionais</h4>"
        )

        msg = f"""Para a concessionária {company_name},
            foram estabelecidos pelo Programa de Exploração a Rodovia (PER)
            os seguintes parâmetros operacionais para os veículos de inspeção de tráfego:"""
        self.md(msg)

        # vit_params = get_vit_params(cnpj)

        self.md("A performance da concessionária está sumarizada na relação abaixo.")

        vit_eval, vit_eval_checks, mean_atrasos, std_atrasos, atrasos_full = (
            get_company_eval(cnpj, date_range)
        )

        eval_msg = ""
        if len(vit_eval_checks["none"]) > 0:
            eval_msg += f"- **{vit_eval_msg['none']}**: meses {', '.join(vit_eval_checks['none'])}\n"
        if len(vit_eval_checks["partial"]) > 0:
            eval_msg += f"- **{vit_eval_msg['partial']}**: meses {', '.join(vit_eval_checks['partial'])}\n"
        if len(vit_eval_checks["all"]) > 0:
            eval_msg += f"- **{vit_eval_msg['all']}**: meses {', '.join(vit_eval_checks['all'])}\n"
        self.md(eval_msg)

        # replace "-" with "Sem dados"
        vit_eval["cumpriu"] = vit_eval["cumpriu"].replace("-", "Sem dados")
        vit_eval["cumpriu"] = vit_eval["cumpriu"].fillna(vit_eval["ST_CUMPRIMENTO"])

        vit_eval_table = (
            vit_eval.rename(
                columns={
                    "DT_MES": "Mês",
                    "tipo": "Tipo de parâmetro",
                    "cumpriu": "Cumprimento",
                    "VL_VALOR": "Valor obtido",
                    "VL_VALOR_ESPERADO": "Valor esperado",
                }
            )
            .drop(columns=["NU_CNPJ", "ST_CUMPRIMENTO"])
            .set_index(["Mês", "Tipo de parâmetro"])
        )

        self.show_table(vit_eval_table)

        _ = st.download_button(
            "Baixar avaliação dos parâmetros operacionais",
            data=vit_eval_table.to_csv().encode("utf-8"),
            file_name=f"vit_parametros_operacionais_{cnpj}.csv",
            mime="text/csv",
            key=f"download_vit_params_eval_{cnpj}",
            icon=":material/download:",
        )

        atrasos_to_download = atrasos_full.drop(
            columns=[
                "NU_CNPJ",
                "CD_PONTO_x",
                "CD_PONTO_y",
                "CD_SENTIDO",
                "VL_DELTA",
                "VL_INTERVALO",
                "VL_INTERVALO_SEGUNDOS",
                "VL_ATRASO_SEGUNDOS",
                "fantasia",
            ]
        ).rename(
            columns={
                "DS_TIPO_PONTO": "Tipo do Ponto",
                "NO_PONTO": "Nome do ponto",
                "NO_SENTIDO": "Sentido",
                "DT_INSTANTE_ANTERIOR": "Início do intervalo",
                "DT_INSTANTE": "Fim do intervalo",
                "DS_PLACA_ANTERIOR": "Placa do VIT inicial",
                "DS_PLACA": "Placa do VIT final",
                "atraso_mins": "Minutos de atraso",
                "CG_LATITUDE": "Latitude",
                "CG_LONGITUDE": "Longitude",
            }
        )

        _ = st.download_button(
            "Baixar relação de todos os atrasos",
            data=atrasos_to_download.to_csv(index=False).encode("utf-8"),
            file_name=f"vit_atrasos_{cnpj}.csv",
            mime="text/csv",
            key=f"download_vit_all_eval_{cnpj}",
            icon=":material/download:",
        )

        self.md(
            f"A média de atrasos foi de {mean_atrasos} minutos para a concessionária, com um desvio padrão de {std_atrasos} minutos."
        )
