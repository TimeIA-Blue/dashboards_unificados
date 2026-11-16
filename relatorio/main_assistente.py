from datetime import date, datetime

import pandas as pd
import pdfkit
import streamlit as st

from client import ch_client
from queries.general import AVAILABLE_COMPANIES_QUERY, AVAILABLE_TIMESTAMPS_QUERY
from relatorio import Reporter, SubReporter, SubReportSection
from relatorio.atendimento import AtendimentoReporter
from relatorio.pedagio import PedagioReporter
from relatorio.radar import RadarReporter
from relatorio.sat import SATReporter
from relatorio.vit import VITReporter

st.set_page_config(page_title="Assistente de fiscalização - ANTT")


@st.cache_data(show_spinner=False)
def load_companies_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    client = ch_client()
    available_companies = client.query_df(AVAILABLE_COMPANIES_QUERY)
    companies_in_system = client.query_df(
        "SELECT * FROM BD_PER.TB_PARAMETROS_CONCESSIONARIAS"
    )
    return companies_in_system, available_companies


@st.cache_data(show_spinner=False)
def load_time_period() -> tuple[date, date]:
    result: pd.DataFrame = (
        ch_client().query_df(AVAILABLE_TIMESTAMPS_QUERY).sort_values("VL_VALOR")
    )
    min_date = datetime.strptime(result.iloc[0]["VL_VALOR"], "%Y-%m-%d").date()
    max_date = datetime.strptime(result.iloc[1]["VL_VALOR"], "%Y-%m-%d").date()
    return min_date, max_date


ch = ch_client()
companies_data, available_companies = load_companies_data()


def reset_report_generation():
    st.session_state.report_number += 1
    st.session_state.report_generated = False
    st.session_state.report_requested = False


def request_report_generation():
    st.session_state.report_generated = True
    st.session_state.report_requested = True


def companies_func(x: str) -> str:
    mask = companies_data["NU_CNPJ"] == x
    return companies_data.loc[mask, "NO_FANTASIA"].values[0]


if "report_generated" not in st.session_state:
    st.session_state.report_generated = False
if "report_requested" not in st.session_state:
    st.session_state.report_requested = False
if "report_number" not in st.session_state:
    st.session_state.report_number = 1

_ = st.title("Assistente de fiscalização")

_ = st.text(
    "Bem-vindo ao assistente de fiscalização. Escolha dentre as opções abaixo para gerar o relatório desejado."
)

min_date, max_date = load_time_period()

selected_date = st.date_input(
    "Período de análise dos dados",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    key="analysis_period",
    on_change=reset_report_generation,
)

companies = st.multiselect(
    "Selecione as concessionárias",
    options=companies_data["NU_CNPJ"].tolist(),
    format_func=companies_func,
    default=companies_data["NU_CNPJ"].tolist()[:1],
    key="companies_selection",
    on_change=reset_report_generation,
)

options = ["Visão geral dos dados", "Parâmetros operacionais", "Anomalias"]
selection = st.pills(
    "Escolha as seções para compor o relatório",
    options,
    selection_mode="multi",
    key="sections_selection",
    on_change=reset_report_generation,
)

datasets = ["Radar", "Pedágio", "VIT", "SAT", "Atendimentos"]
dataset_selection = st.pills(
    "Selecione os conjuntos de dados",
    datasets,
    selection_mode="multi",
    key="datasets_selection",
    on_change=reset_report_generation,
)

EMPTY_SELECTION_MSG = "**:red[nenhuma opção foi selecionada]**"
sections_msg = (
    ", ".join(x for x in selection) if len(selection) > 0 else EMPTY_SELECTION_MSG
)
datasets_msg = (
    ", ".join(x for x in dataset_selection)
    if len(dataset_selection) > 0
    else EMPTY_SELECTION_MSG
)
_ = st.markdown(f"Seções do relatório: {sections_msg}.")
_ = st.markdown(f"Conjuntos de dados selecionados: {datasets_msg}.")

structures = [
    "Conjunto de Dados → Concessionárias",
    "Concessionária → Conjunto de Dados",
]
preffered_strucutre = st.pills(
    "Estruturação do relatório",
    structures,
    selection_mode="single",
    key="structure_selection",
    on_change=reset_report_generation,
    default=structures[0],
)
company_first = preffered_strucutre == structures[1]


def generate_report():
    if not selection or not dataset_selection or not companies:
        _ = st.error(
            "Por favor, selecione ao menos uma seção e um conjunto de dados para gerar o relatório."
        )
        return

    subreporters_cls: list[type[SubReporter]] = []
    current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    generated_report_str = (
        f"Relatório técnico operacional\nGerado em {current_time}\n\n"
    )
    generated_html_report = f"<p>{generated_report_str}</p>"
    if "Atendimentos" in dataset_selection:
        subreporters_cls.append(AtendimentoReporter)
    if "Radar" in dataset_selection:
        subreporters_cls.append(RadarReporter)
    if "SAT" in dataset_selection:
        subreporters_cls.append(SATReporter)
    if "Pedágio" in dataset_selection:
        subreporters_cls.append(PedagioReporter)
    if "VIT" in dataset_selection:
        subreporters_cls.append(VITReporter)

    selected_sections: list[SubReportSection] = []
    if "Visão geral dos dados" in selection:
        selected_sections.append(SubReportSection.VISAO_GERAL)
    if "Parâmetros operacionais" in selection:
        selected_sections.append(SubReportSection.PARAMETROS_OPERACIONAIS)
    if "Anomalias" in selection:
        selected_sections.append(SubReportSection.ANOMALIAS)

    reporter = Reporter(
        subreporters_cls,
        companies,
        selected_sections,
        company_first=company_first,
        companies_data=companies_data,
    )

    html = reporter.build_report(selected_date)  # ty: ignore[invalid-argument-type]
    generated_html_report += f"\n{html}"
    _ = st.success("Relatório gerado com sucesso!")
    _ = st.markdown("---")

    css_file_path = "report_styling.css"
    with open(css_file_path, "r", encoding="utf-8") as css_file:
        css_content = css_file.read()
    custom_css = f"""
    <style>
    {css_content}
    </style>
    """

    full_html = f"""
    <html>
    <head>
    <meta charset='utf-8'>
    <title>Relatório técnico operacional</title>
    {custom_css}
    </head>
    <body>
    {generated_html_report}
    </body>
    </html>
    """

    pdf_bytes = pdfkit.from_string(full_html, False)
    date_sort = datetime.now().strftime("%Y_%m_%d")
    concessionarias_title = (
        "Multiplas" if len(companies) > 1 else companies_func(companies[0])
    )
    datasets_title = "Multiplos" if len(dataset_selection) > 1 else dataset_selection[0]
    file_name = f"{date_sort}_{concessionarias_title}_{datasets_title}.pdf"
    if len(file_name) > 100:
        file_name = f"{date_sort}.pdf"
    st.download_button(
        label="Baixar relatório completo",
        data=pdf_bytes,
        file_name=file_name,
        mime="application/pdf",
        key="download_pdf_report",
    )


_ = st.button(
    "Gerar relatório", key="generate_report_button", on_click=request_report_generation
)

_ = st.markdown("---")

report_container = st.container()

if st.session_state.report_generated:
    if st.session_state.report_requested:
        with st.spinner("Gerando relatório..."), report_container:
            generate_report()
        st.session_state.report_requested = False
    else:
        with report_container:
            generate_report()
