import pandas as pd
import streamlit as st
from sqlalchemy import text

conn = st.session_state.conn

df = conn.query(
    """
    SELECT concessionaria.no_fantasia, sat.*, sat_tipo.nome AS tipo_interrup_nome
    FROM sat
    INNER JOIN concessionaria ON sat.cnpj = concessionaria.cnpj
    INNER JOIN sat_tipo ON sat.tipo_interrup = sat_tipo.id
""",
    ttl=0,
)

# salvando o mapeamento entre CNPJ e nome da concessionária
# os nomes e cnpjs são únicos, portanto podemos assumir a correspondência
cnpj_map = conn.query("SELECT * FROM concessionaria", ttl=0)
# to dict
cnpj_map = dict(zip(cnpj_map["cnpj"], cnpj_map["no_fantasia"]))

# salvando os enums de tipos
sat_tipo = conn.query("SELECT * FROM sat_tipo", ttl=0)
sat_tipo = dict(zip(sat_tipo["id"], sat_tipo["nome"]))

# retirando as coluna de CNPJ e tipo do DataFrame
df = df.drop(columns=["cnpj", "tipo_interrup"])

# reorderando as colunas
df = df[["no_fantasia", "tipo_interrup_nome", "tempo_max_interrup", "pct_max_interrup"]]

# mapeamento dos nomes das colunas
data_config = {
    "no_fantasia": st.column_config.SelectboxColumn(
        options=list(cnpj_map.values()),
        required=True,
        label="Concessionária",
    ),
    "tipo_interrup_nome": st.column_config.SelectboxColumn(
        options=list(sat_tipo.values()),
        required=True,
        label="Tipo de interrupção",
    ),
    "tempo_max_interrup": st.column_config.NumberColumn(
        min_value=1,
        label="Tempo máximo de interrupção por mês (horas)",
    ),
    "pct_max_interrup": st.column_config.NumberColumn(
        min_value=0.0,
        max_value=100.0,
        label="Percentual de interrupção permitida",
    ),
}

st.title("SAT")

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="sat_editor",
    num_rows="dynamic",
)

# lógica de validação


def validate(data):
    # verifica se o CNPJ é único
    if data["cnpj"].duplicated().any():
        st.error("Há concessionárias duplicadas.")
        return False

    # verificação linha a linha, para maior facilidade do usuário
    for _, row in data.iterrows():
        if row["tempo_max_interrup"] <= 0:
            st.error(
                f"O tempo máximo de interrupção para concessionária **{cnpj_map[row['cnpj']]}** deve ser maior que a 0."
            )
            return False

        if row["pct_max_interrup"] < 0 or row["pct_max_interrup"] > 100:
            st.error(
                f"O percentual de interrupção para concessionária **{cnpj_map[row['cnpj']]}** deve estar entre 0 e 100."
            )
            return False

        # se o tipo for Equipamento ou Sistema, ou ambos, tem que ter tempo máximo de interrupção
        if row["tipo_interrup"] in [1, 2, 3, 5] and (
            row["tempo_max_interrup"] == 0 or pd.isna(row["tempo_max_interrup"])
        ):
            st.error(
                f"O tempo máximo de interrupção para concessionária **{cnpj_map[row['cnpj']]}** deve ser maior que 0."
            )
            return False

        # se o tipo envolver Sistem com %, o percentual deve ser maior que 0
        if row["tipo_interrup"] in [4, 5] and (
            row["pct_max_interrup"] == 0 or pd.isna(row["pct_max_interrup"])
        ):
            st.error(
                f"O percentual de interrupção para concessionária **{cnpj_map[row['cnpj']]}** deve ser maior que 0."
            )
            return False

    return True


def save_data():
    # revertendo os dados
    data = edited_df.copy()
    data["cnpj"] = data["no_fantasia"].map({v: k for k, v in cnpj_map.items()})
    data["tipo_interrup"] = data["tipo_interrup_nome"].map(
        {v: k for k, v in sat_tipo.items()}
    )

    # removendo as colunas que não são necessárias
    data = data.drop(columns=["no_fantasia", "tipo_interrup_nome"])

    # validando
    if not validate(data):
        return

    # como não há chaves estrangeiras, podemos simplesmente deletar
    # a tabela antiga e inserir a nova
    # persistindo os dados no banco
    with conn.session as session:
        # ainda assim, vamos habilitar as chaves estrangeiras
        # pois devemos verificar os ids dos tipos
        session.execute(text("PRAGMA foreign_keys = ON;"))

        # deletando os dados antigos
        session.execute(text("DELETE FROM sat;"))
        # upsert
        for row in data.itertuples(index=False):
            # dificilmente vai dar conflito
            session.execute(
                text("""
                    INSERT INTO sat (cnpj, tipo_interrup, tempo_max_interrup, pct_max_interrup)
                    VALUES (:cnpj, :tipo_interrup, :tempo_max_interrup, :pct_max_interrup)
                    ON CONFLICT(cnpj) DO UPDATE SET
                        tipo_interrup=excluded.tipo_interrup,
                        tempo_max_interrup=excluded.tempo_max_interrup,
                        pct_max_interrup=excluded.pct_max_interrup
                """),
                {
                    "cnpj": row.cnpj,
                    "tipo_interrup": row.tipo_interrup,
                    "tempo_max_interrup": row.tempo_max_interrup,
                    "pct_max_interrup": row.pct_max_interrup,
                },
            )

        session.commit()

    st.success("Parâmetros de **SAT** atualizados com sucesso!")


if st.button("Salvar"):
    save_data()
