import sqlite3

import streamlit as st

from .create import create_db
from .populate import populate_db


# essa rotina cria o banco de dados do gerenciador caso ele ainda não exista
@st.cache_resource
def init_db():
    # poderíamos usar o conector do próprio streamlit
    # por padronização, deixamos o sqlite3 mesmo (totalmente compatível)
    conn = sqlite3.connect("data/example.db")
    create_db(conn)
    populate_db(conn)
    conn.close()
