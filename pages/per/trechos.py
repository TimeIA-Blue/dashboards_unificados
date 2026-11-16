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
    "nome": "Nome do trecho",
    "rodovia": "Número da rodovia",
    "km_inicial": "KM Inicial",
    "km_final": "KM Final",
}

st.title("Trechos")

df = conn.query(f"SELECT {','.join(data_config.keys())} FROM trechos", ttl=0)

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="trechos_editor",
    num_rows="dynamic",
)

# lógica de validação


def validate(data):
    # verifica se o nome é único
    if data["nome"].duplicated().any():
        st.error("Nome deve ser único.")
        return False

    # verifica se há trechos conflitantes
    conflicts = set()
    for i, r_i in data.iterrows():
        every_other = data.drop(index=i)
        for j, r_j in every_other.iterrows():
            if r_j["rodovia"] == r_i["rodovia"] and (
                r_j["km_inicial"] < r_i["km_final"]
                or r_j["km_final"] > r_i["km_inicial"]
            ):
                names = [r_i["nome"], r_j["nome"]]
                names.sort()
                conflicts.add((names[0], names[1]))
    if len(conflicts) > 0:
        err_str = "Os seguintes trechos entram em conflito:"
        for c in conflicts:
            err_str += f"\\\n{c[0]} e {c[1]}"
        st.error(err_str)
        return False

    return True


def save_data():
    # validação dos dados
    if not validate(edited_df):
        return

    # encontrando nomes que foram removidos
    old_trechos = set(df["nome"])
    new_trechos = set(edited_df["nome"])
    deleted_trechos = old_trechos - new_trechos

    with conn.session as session:
        # IMPORTANTE: habilitando as chaves estrangeiras
        session.execute(text("PRAGMA foreign_keys = ON"))
        # deletando apenas os CNPJs que foram removidos
        for trecho in deleted_trechos:
            try:
                session.execute(
                    text("DELETE FROM trechos WHERE nome = :t"), {"t": trecho}
                )
            except Exception as e:
                st.error(
                    f"Erro ao remover trecho {trecho}.\nUm trecho só pode ser removido se não estiver associado a nenhum outro registro."
                )
                return

        # upsert
        for row in edited_df.itertuples(index=False):
            session.execute(
                text("""
                    INSERT INTO trechos (nome, rodovia, km_inicial, km_final)
                    VALUES (:nome, :rodovia, :kmi, :kmf)
                    ON CONFLICT(nome) DO UPDATE SET rodovia=excluded.rodovia, km_inicial=excluded.km_inicial, km_final=excluded.km_final
                """),
                {
                    "nome": row.nome,
                    "rodovia": row.rodovia,
                    "kmi": row.km_inicial,
                    "kmf": row.km_final,
                },
            )
        session.commit()
    st.success("Relação de **trechos** atualizada com sucesso!")


if st.button("Salvar"):
    save_data()
