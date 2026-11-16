import streamlit as st

from database.setup import init_db

init_db()

conn = st.connection("sqlite")
st.session_state.conn = conn

st.set_page_config(
    layout="wide",
    page_title="Gerenciador de parâmetros operacionais",
    page_icon="favicon.png",
)

st.header("Gerenciador de parâmetros operacionais")

st.markdown(
    """Você está na página inicial do **gerenciador de parâmetros operacionais**.
A navegação pelo sistema deve ser feita utilizando a barra de menus superior.

## Navegação
### Configurações
* Para **adicionar uma concessionária** ainda não contemplada no sistema, ou remover,
utilize o caminho _Configurações > Concessionárias_.
* Para **sincronizar o sistema** com as visualizações e análises, utilize o caminho
_Configurações > Sincronização_.

### Parâmetros
Para alterar os parâmetros operacionais, utilize o caminho _Parâmetros_ no menu superior,
e escolha o conjunto de dados desejado. Atualmente, o sistema contempla os dados de:
* Radar
* Pedágio
* SAT
* VIT
* Atendimento

Lembre-se de **sincronizar o sistema** após alterar os parâmetros operacionais,
utilizando o caminho _Configurações > Sincronização_.
"""
)

# * Para **verificar o significado** dos nomes utilizados no sistema, utilize o caminho _Configurações > Glossário_.
