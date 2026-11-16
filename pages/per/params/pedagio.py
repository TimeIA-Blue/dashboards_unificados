import streamlit as st
from sqlalchemy import text

conn = st.session_state.conn

# preparando os dados
df = conn.query(
    """
    SELECT concessionaria.no_fantasia, pedagio.*, pedagio_tipo.nome AS tipo_interrup_nome
    FROM pedagio
    INNER JOIN concessionaria ON pedagio.cnpj = concessionaria.cnpj
    INNER JOIN pedagio_tipo ON pedagio.tipo_interrup = pedagio_tipo.id
""",
    ttl=0,
)

# salvando o mapeamento entre CNPJ e nome da concessionária
# os nomes e cnpjs são únicos, portanto podemos assumir a correspondência
cnpj_map = conn.query("SELECT * FROM concessionaria", ttl=0)
# to dict
cnpj_map = dict(zip(cnpj_map["cnpj"], cnpj_map["no_fantasia"]))

# salvando os enums de tipos
pedagio_tipo = conn.query("SELECT * FROM pedagio_tipo", ttl=0)
pedagio_tipo = dict(zip(pedagio_tipo["id"], pedagio_tipo["nome"]))

# retirando as coluna de CNPJ e tipo do DataFrame
df = df.drop(columns=["cnpj", "tipo_interrup"])

# reorderando as colunas
df = df[["no_fantasia", "tipo_interrup_nome", "tempo_max_interrup"]]

st.title("Pedágio")

data_config = {
    "no_fantasia": st.column_config.SelectboxColumn(
        options=list(cnpj_map.values()),
        required=True,
        label="Concessionária",
    ),
    "tipo_interrup_nome": st.column_config.SelectboxColumn(
        options=list(pedagio_tipo.values()),
        required=True,
        label="Tipo de interrupção",
    ),
    "tempo_max_interrup": st.column_config.NumberColumn(
        min_value=1,
        required=True,
        label="Tempo máximo de interrupção por mês (horas)",
    ),
}

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="pedagio_editor",
    num_rows="dynamic",
)


# lógica de validação
def validate(data):
    # verifica se os CNPJ são únicos
    if data["cnpj"].duplicated().any():
        st.error("Há concessionárias duplicadas.")
        return False

    # verifica se o tempo máximo de interrupção é > 0
    for _, row in data.iterrows():
        if row["tempo_max_interrup"] <= 0:
            st.error(
                f"O tempo máximo de interrupção deve ser maior que 0 para a concessionária **{cnpj_map[row['cnpj']]}**."
            )
            return False

    return True


def save_data():
    # revertendo os dados
    data = edited_df.copy()
    data["cnpj"] = data["no_fantasia"].map({v: k for k, v in cnpj_map.items()})
    data["tipo_interrup"] = data["tipo_interrup_nome"].map(
        {v: k for k, v in pedagio_tipo.items()}
    )

    # removendo as colunas que não são necessárias
    data = data.drop(columns=["no_fantasia", "tipo_interrup_nome"])

    if not validate(data):
        return

    # como não há chaves estrangeiras, podemos simplesmente deletar a antiga e substituir pela nova
    with conn.session as session:
        # habilitando chaves estrangeiras para verificação dos tipos
        session.execute(text("PRAGMA foreign_keys = ON;"))

        # deletando a tabela antiga
        session.execute(text("DELETE FROM pedagio;"))
        # upsert
        for row in data.itertuples(index=False):
            session.execute(
                text("""
                    INSERT INTO pedagio (cnpj, tipo_interrup, tempo_max_interrup)
                    VALUES (:cnpj, :tipo_interrup, :tempo_max_interrup)
                    ON CONFLICT(cnpj) DO UPDATE SET
                        tipo_interrup = excluded.tipo_interrup,
                        tempo_max_interrup = excluded.tempo_max_interrup
                """),
                {
                    "cnpj": row.cnpj,
                    "tipo_interrup": row.tipo_interrup,
                    "tempo_max_interrup": row.tempo_max_interrup,
                },
            )

        session.commit()

    st.success("Parâmetros de **pedágio** atualizados com sucesso!")


if st.button("Salvar"):
    save_data()
