import pandas as pd
import streamlit as st
from sqlalchemy import text

from database.setup import init_db

init_db()

conn = st.connection("sqlite")
st.session_state.conn = conn

st.set_page_config(
    layout="wide",
    page_title="Gerenciador de parâmetros operacionais",
    page_icon="favicon.png",
)
conn = st.session_state.conn

# mapeamento dos nomes das colunas
data_config = {
    "cnpj": "CNPJ",
    "no_fantasia": "Nome fantasia",
}

st.title("Concessionárias")

df = conn.query("SELECT * FROM concessionaria", ttl=0)

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="concessionarias_editor",
    num_rows="dynamic",
)


# lógica de validação
def validate(data):
    # verifica se o CNPJ é único
    if data["cnpj"].duplicated().any():
        st.error("Há CNPJs duplicados.")
        return False

    # verifica se o nome fantasia é único
    if data["no_fantasia"].duplicated().any():
        st.error("Há nomes fantasia duplicados.")
        return False

    for _, row in data.iterrows():
        if len(row["cnpj"]) == 0:
            st.error(
                "CNPJ vazio encontrado.\n\nPor favor preencha todos os campos ou remova a(s) linha(s) problemática(s)."
            )
            return False

        if len(row["no_fantasia"]) == 0:
            st.error(
                "Nome fantasia vazio encontrado.\n\nPor favor preencha todos os campos ou remova a(s) linha(s) problemática(s)."
            )
            return False

        if (
            not isinstance(row["cnpj"], str)
            or len(row["cnpj"]) != 14
            or not row["cnpj"].isdigit()
        ):
            st.error(
                f"CNPJ inválido: **{row['cnpj']}**. O valor deve conter exatamente 14 dígitos números."
            )
            return False

        if len(row["no_fantasia"]) > 1024:
            st.error(
                f"Nome fantasia excessivamente longo para CNPJ: **{row['cnpj']}**."
            )
            return False

        if pd.isna(row["no_fantasia"]) or pd.isna(row["cnpj"]):
            st.error(
                "Há campos vazios na tabela.\n\nPor favor preencha todos os campos ou remova a(s) linha(s) problemática(s)."
            )
            return False

    return True


def save_data():
    # validação dos dados
    if not validate(edited_df):
        return

    # encontrando CNPJs que foram removidos
    old_cnpjs = set(df["cnpj"])
    new_cnpjs = set(edited_df["cnpj"])
    deleted_cnpjs = old_cnpjs - new_cnpjs

    with conn.session as session:
        # IMPORTANTE: habilitando as chaves estrangeiras
        session.execute(text("PRAGMA foreign_keys = ON"))
        # deletando apenas os CNPJs que foram removidos
        for cnpj in deleted_cnpjs:
            try:
                session.execute(
                    text("DELETE FROM concessionaria WHERE cnpj = :cnpj"),
                    {"cnpj": cnpj},
                )
            except Exception as e:
                st.error(
                    f"Erro ao remover concessionária de CNPJ {cnpj}.\n\nUma concessionária só pode ser removida se não estiver associada a nenhum outro registro.\n\nAtualize a página para reverter os dados."
                )
                return

        # upsert
        for row in edited_df.itertuples(index=False):
            session.execute(
                text("""
                    INSERT INTO concessionaria (cnpj, no_fantasia)
                    VALUES (:cnpj, :no_fantasia)
                    ON CONFLICT(cnpj) DO UPDATE SET no_fantasia=excluded.no_fantasia
                """),
                {"cnpj": row.cnpj, "no_fantasia": row.no_fantasia},
            )
        session.commit()
    st.success("Relação de **concessionárias** atualizada com sucesso!")


if st.button("Salvar"):
    save_data()
