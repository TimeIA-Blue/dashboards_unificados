import pandas as pd
import streamlit as st
from sqlalchemy import text

conn = st.session_state.conn

# preparando os dados
df = conn.query(
    """
    SELECT concessionaria.no_fantasia, vit.*
    FROM vit
    INNER JOIN concessionaria ON vit.cnpj = concessionaria.cnpj
""",
    ttl=0,
)

# salvando o mapeamento entre CNPJ e nome da concessionária
# os nomes e cnpjs são únicos, portanto podemos assumir a correspondência
cnpj_map = conn.query("SELECT * FROM concessionaria", ttl=0)
cnpj_map = dict(zip(cnpj_map["cnpj"], cnpj_map["no_fantasia"]))

# retirando as coluna de CNPJ do DataFrame
df = df.drop(columns=["cnpj"])

st.title("Veículos de Inspeção de Tráfego (VIT)")

data_config = {
    "no_fantasia": st.column_config.SelectboxColumn(
        options=list(cnpj_map.values()),
        required=True,
        label="Concessionária",
    ),
    "vel_med": st.column_config.NumberColumn(
        min_value=1,
        label="Velocidade média (km/h)",
    ),
    "soma_quatro_atrasos": st.column_config.NumberColumn(
        min_value=1,
        label="Σ atrasos de 4 viaturas (min)",
    ),
    "it": st.column_config.NumberColumn(
        min_value=1,
        label="Intervalo de tempo de ciclo de inspeção (min)",
    ),
}

edited_df = st.data_editor(
    df,
    use_container_width=True,
    column_config=data_config,
    key="vit_editor",
    num_rows="dynamic",
)


def validate(data):
    # verifica se o CNPJ é único
    if data["cnpj"].duplicated().any():
        st.error("Há concessionárias duplicadas.")
        return False

    for _, row in data.iterrows():
        # verifica se a velocidade média é > 0
        if row["vel_med"] <= 0:
            st.error(
                f"A velocidade média deve ser maior que 0 para a concessionária **{cnpj_map[row['cnpj']]}**."
            )
            return False

        # verifica se a soma dos atrasos é > 0
        if row["soma_quatro_atrasos"] <= 0:
            st.error(
                f"A soma dos atrasos deve ser maior que 0 para a concessionária **{cnpj_map[row['cnpj']]}**."
            )
            return False

        # verifica se o intervalo de tempo é > 0
        if row["it"] <= 0:
            st.error(
                f"O intervalo de tempo deve ser maior que 0 para a concessionária **{cnpj_map[row['cnpj']]}**."
            )
            return False

        # verifica se há algum cnpj sem valores algum
        if (not pd.isna(row["cnpj"])) and (
            pd.isna(row["vel_med"])
            and pd.isna(row["soma_quatro_atrasos"])
            and pd.isna(row["it"])
        ):
            st.error(
                f"Não há parâmetros cadastrados para a concessionária **{cnpj_map[row['cnpj']]}**. Insira ao menos um ou a remova da tabela."
            )
            return False

    return True


def save_data():
    data = edited_df.copy()
    data["cnpj"] = data["no_fantasia"].map({v: k for k, v in cnpj_map.items()})

    # removendo no_fantasia
    data = data.drop(columns=["no_fantasia"])

    if not validate(data):
        return

    with conn.session as session:
        # em teoria, não há possibilidade de infração aqui,
        # mas mantemos a verificação de chave estrangeira para garantir a integridade
        session.execute(text("PRAGMA foreign_keys = ON;"))

        # deletando os dados antigos
        session.execute(text("DELETE FROM vit;"))

        # upsert
        for row in data.itertuples(index=False):
            session.execute(
                text("""
                    INSERT INTO vit (cnpj, vel_med, soma_quatro_atrasos, it)
                    VALUES (:cnpj, :vel_med, :soma_quatro_atrasos, :it)
                    ON CONFLICT(cnpj) DO UPDATE SET
                        vel_med=excluded.vel_med,
                        soma_quatro_atrasos=excluded.soma_quatro_atrasos,
                        it=excluded.it
                """),
                {
                    "cnpj": row.cnpj,
                    "vel_med": row.vel_med,
                    "soma_quatro_atrasos": row.soma_quatro_atrasos,
                    "it": row.it,
                },
            )

        session.commit()

    st.success("Parâmetros de **VIT** atualizados com sucesso!")


if st.button("Salvar"):
    save_data()
