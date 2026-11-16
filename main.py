from collections.abc import Mapping, Sequence

import streamlit as st
from streamlit.commands.navigation import PageType, SectionHeader

if not st.secrets.environment.is_development:
    print("Lógica de autenticação ainda não foi implementada")

st.set_page_config(
    layout="wide",
    page_title="Gerenciador de parâmetros operacionais",
    page_icon="favicon.png",
)

pages: Sequence[PageType] | Mapping[SectionHeader, Sequence[PageType]] = {
    "Assistente de Fiscalização": [
        st.Page(
            "relatorio/main_assistente.py",
            title="Gerador de relátorios",
            url_path="assistente",
        ),
    ],
    "Gerenciador do PER": [
        st.Page("pages/per/home.py", title="Menu Principal", url_path="per"),
        st.Page("pages/per/concessionarias.py", title="Relação de Concessionárias"),
        st.Page("pages/per/trechos.py", title="Relação de Trechos"),
        st.Page("pages/per/sync.py", title="Sincronização"),
        st.Page("pages/per/params/atendimento.py", title="Configuração: Atendimento"),
        st.Page("pages/per/params/radar.py", title="Configuração: Radar"),
        st.Page("pages/per/params/pedagio.py", title="Configuração: Pedágio"),
        st.Page("pages/per/params/sat.py", title="Configuração: SAT"),
        st.Page("pages/per/params/vit.py", title="Configuração: VIT"),
    ],
    "Visualização com Grid Hexagonal": [
        st.Page("pages/h3/main_h3.py", title="Menu Principal", url_path="h3"),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
