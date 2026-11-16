import streamlit as st
from sqlalchemy import text

conn = st.session_state.conn

df = conn.query(
    """
    SELECT concessionaria.no_fantasia, atendimento.*, atendimento_tipo.nome AS tipo_parametro_nome, trechos.nome AS nome_trecho
    FROM atendimento
    INNER JOIN concessionaria ON atendimento.cnpj = concessionaria.cnpj
    INNER JOIN atendimento_tipo ON atendimento.tipo_parametro = atendimento_tipo.id
    LEFT JOIN trechos ON atendimento.trecho_id = trechos.id
""",
    ttl=0,
)

# salvando o mapeamento entre CNPJ e nome da concessionária
# os nomes e cnpjs são únicos, portanto podemos assumir a correspondência
cnpj_map = conn.query("SELECT * FROM concessionaria", ttl=0)
# to dict
cnpj_map = dict(zip(cnpj_map["cnpj"], cnpj_map["no_fantasia"]))

trecho_map = conn.query("SELECT * FROM trechos", ttl=0)
# dict
trecho_map = dict(zip(trecho_map["id"], trecho_map["nome"]))

servico_por_recurso = {
    "Motocicleta": "Mecânico",
    "Guincho Leve": "Mecânico",
    "Guincho Pesado": "Mecânico",
    "Ambulância C": "Médico",
    "Ambulância D": "Médico",
}

# salvando os enums de tipos
atendimento_tipo = conn.query("SELECT * FROM atendimento_tipo", ttl=0)
atendimento_tipo = dict(zip(atendimento_tipo["id"], atendimento_tipo["nome"]))

# retirando as coluna de CNPJ e tipo do DataFrame
df = df.drop(columns=["id", "cnpj", "trecho_id", "tipo_servico", "tipo_parametro"])


# reorderando as colunas
df = df[
    [
        "no_fantasia",
        "rodovia",
        "nome_trecho",
        "tipo_recurso",
        "tipo_parametro_nome",
        "valor",
    ]
]

# mapeamento dos nomes das colunas
data_config = {
    "no_fantasia": st.column_config.SelectboxColumn(
        options=list(cnpj_map.values()),
        required=True,
        label="Concessionária",
    ),
    "rodovia": st.column_config.NumberColumn(
        min_value=0,
        max_value=9999,
        label="Rodovia",
        required=False,
    ),
    "nome_trecho": st.column_config.SelectboxColumn(
        options=list(trecho_map.values()),
        required=False,
        label="Trecho",
    ),
    "tipo_recurso": st.column_config.SelectboxColumn(
        options=list(servico_por_recurso.keys()),
        required=True,
        label="Tipo de Recurso",
    ),
    "tipo_parametro_nome": st.column_config.SelectboxColumn(
        options=list(atendimento_tipo.values()),
        required=True,
        label="Tipo de Parâmetro",
    ),
    "valor": st.column_config.NumberColumn(
        min_value=0,
        max_value=9999,
        label="Valor",
        required=True,
    ),
}

st.title("Atendimento")

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="atendimento_editor",
    num_rows="dynamic",
)

# lógica de validação


def validate(data):
    # verificando duplicidade
    chave = data.columns[:-1]
    if data[chave].duplicated().any():
        st.error("Há registros duplicados.")
        return False

    # verificação linha a linha, para maior facilidade do usuário
    for _, row in data.iterrows():
        pass

    return True


def save_data():
    # revertendo os dados
    data = edited_df.copy()

    idx_trecho_definido = data[~data["nome_trecho"].isna()].index
    data.loc[idx_trecho_definido, "rodovia"] = None

    # validando
    if not validate(data):
        return

    data["cnpj"] = data["no_fantasia"].map({v: k for k, v in cnpj_map.items()})
    data["trecho_id"] = data["nome_trecho"].map({v: k for k, v in trecho_map.items()})
    data["tipo_servico"] = data["tipo_recurso"].map(
        {k: v for k, v in servico_por_recurso.items()}
    )
    data["tipo_parametro"] = data["tipo_parametro_nome"].map(
        {v: k for k, v in atendimento_tipo.items()}
    )

    # removendo as colunas que não são necessárias
    data = data.drop(columns=["no_fantasia", "nome_trecho", "tipo_parametro_nome"])

    # como não há chaves estrangeiras, podemos simplesmente deletar
    # a tabela antiga e inserir a nova
    # persistindo os dados no banco
    with conn.session as session:
        # ainda assim, vamos habilitar as chaves estrangeiras por precaução
        session.execute(text("PRAGMA foreign_keys = ON;"))

        # deletando os dados antigos
        session.execute(text("DELETE FROM atendimento;"))
        # upsert
        for row in data.itertuples(index=False):
            session.execute(
                text("""
                    INSERT INTO atendimento (cnpj, rodovia, trecho_id, tipo_servico, tipo_recurso, tipo_parametro, valor)
                    VALUES (:cnpj, :rodovia, :trecho_id, :tipo_servico, :tipo_recurso, :tipo_parametro, :valor)
                    ON CONFLICT(cnpj, rodovia, trecho_id, tipo_servico, tipo_recurso, tipo_parametro) DO UPDATE SET
                        valor=excluded.valor
                """),
                {
                    "cnpj": row.cnpj,
                    "rodovia": row.rodovia,
                    "trecho_id": row.trecho_id,
                    "tipo_servico": row.tipo_servico,
                    "tipo_recurso": row.tipo_recurso,
                    "tipo_parametro": row.tipo_parametro,
                    "valor": row.valor,
                },
            )

        session.commit()

    st.success("Parâmetros de **atendimento** atualizados com sucesso!")


if st.button("Salvar"):
    save_data()
