import datetime

import streamlit as st

from client import ch_client
from database.setup import init_db
from setup import get_general_logger, get_query_logger

init_db()

conn = st.connection("sqlite")
st.session_state.conn = conn

st.set_page_config(
    layout="wide",
    page_title="Gerenciador de parâmetros operacionais",
    page_icon="favicon.png",
)
conn = st.session_state.conn


# função auxiliar para gerar um número de versão e uma timestamp
def gen_version_with_time(curr_version):
    version = curr_version + 1
    timestamp = datetime.datetime.now()
    return version, timestamp


def insert_radar(ch_client):
    data = conn.query("SELECT * FROM radar", ttl=0)

    # pegando a versão atual dos dados
    # command ao invés de query pois pegamos uma única linha de dados (https://clickhouse.com/docs/integrations/python)
    # já vem até no tipo certo (int)
    max_version = ch_client.command(
        "SELECT max(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_RADAR"
    )

    # gerando nova versão e horário da criação
    new_version, creation_timestamp = gen_version_with_time(max_version)

    # prerando os dados
    # aqui, não verifico se os dados presentes no clickhouse são iguais aos inseridos
    # atualizando apenas quando são diferentes
    # é uma possível otimização futura
    new_data = []
    for _, row in data.iterrows():
        new_row = [
            row["cnpj"],
            row["tipo_interrup"],
            row["tempo_max_interrup"],
            row["pct_max_interrup"],
            new_version,
            creation_timestamp,
        ]

        new_data.append(new_row)

    ch_client.insert(
        "BD_PER.TB_PARAMETROS_RADAR",
        new_data,
        column_names=[
            "NU_CNPJ",
            "CD_TIPO_INTERRUPCAO",
            "VL_TEMPO_MAX_INTERRUPCAO",
            "VL_PCT_MAX_INTERRUPCAO",
            "CD_DEPLOY_ID",
            "DT_DEPLOY_TIMESTAMP",
        ],
    )

    st.success("Parâmetros de **radar** atualizados com sucesso.")


def insert_pedagio(ch_client):
    data = conn.query("SELECT * FROM pedagio", ttl=0)

    max_version = ch_client.command(
        "SELECT max(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_PEDAGIO"
    )

    new_version, creation_timestamp = gen_version_with_time(max_version)

    new_data = []
    for _, row in data.iterrows():
        new_row = [
            row["cnpj"],
            row["tipo_interrup"],
            row["tempo_max_interrup"],
            new_version,
            creation_timestamp,
        ]

        new_data.append(new_row)

    ch_client.insert(
        "BD_PER.TB_PARAMETROS_PEDAGIO",
        new_data,
        column_names=[
            "NU_CNPJ",
            "CD_TIPO_INTERRUPCAO",
            "VL_TEMPO_MAX_INTERRUPCAO",
            "CD_DEPLOY_ID",
            "DT_DEPLOY_TIMESTAMP",
        ],
    )

    st.success("Parâmetros de **pedágio** atualizados com sucesso.")


def insert_vit(ch_client):
    data = conn.query("SELECT * FROM vit", ttl=0)

    max_version = ch_client.command(
        "SELECT max(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_VIT"
    )

    new_version, creation_timestamp = gen_version_with_time(max_version)
    new_data = []
    for _, row in data.iterrows():
        new_row = [
            row["cnpj"],
            row["vel_med"],
            row["soma_quatro_atrasos"],
            row["it"],
            new_version,
            creation_timestamp,
        ]

        new_data.append(new_row)

    ch_client.insert(
        "BD_PER.TB_PARAMETROS_VIT",
        new_data,
        column_names=[
            "NU_CNPJ",
            "VL_VELOCIDADE_MEDIA",
            "VL_SOMA_QUATRO_ATRASOS",
            "VL_INTERVALO",
            "CD_DEPLOY_ID",
            "DT_DEPLOY_TIMESTAMP",
        ],
    )

    st.success("Parâmetros de **VIT** atualizados com sucesso.")


def insert_atendimento(ch_client):
    data = conn.query(
        """SELECT
        a.cnpj, a.rodovia AS rodovia_1, a.tipo_servico, a.tipo_recurso, a.tipo_parametro, a.valor,
        t.rodovia AS rodovia_2, t.km_inicial, t.km_final, t.nome AS nome_trecho
        FROM atendimento a LEFT JOIN trechos t
        ON a.trecho_id = t.id""",
        ttl=0,
    )
    data["rodovia"] = data["rodovia_1"].fillna(data["rodovia_2"])
    data.drop(columns=["rodovia_1", "rodovia_2"], inplace=True)

    (new_version, creation_timestamp) = ch_client.command(
        "SELECT (MAX(CD_DEPLOY_ID) + 1) AS next_deploy_id, now64(3, 'UTC') FROM BD_PER.TB_PARAMETROS_ATENDIMENTO SETTINGS date_time_output_format = 'iso'"
    )
    creation_timestamp = datetime.datetime.fromisoformat(creation_timestamp)

    data["deploy_id"] = new_version
    data["deploy_timestamp"] = creation_timestamp
    data = data[
        [
            "cnpj",
            "rodovia",
            "km_inicial",
            "km_final",
            "tipo_recurso",
            "tipo_parametro",
            "valor",
            "deploy_id",
            "deploy_timestamp",
            "tipo_servico",
            "nome_trecho",
        ]
    ]
    ch_client.insert_df(
        "BD_PER.TB_PARAMETROS_ATENDIMENTO",
        data,
        column_names=[
            "NU_CNPJ",
            "CD_RODOVIA",
            "VL_KM_INICIAL",
            "VL_KM_FINAL",
            "CD_TIPO_RECURSO",
            "CD_TIPO_PARAMETRO",
            "VL_VALOR",
            "CD_DEPLOY_ID",
            "DT_DEPLOY_TIMESTAMP",
            "DS_TIPO_SERVICO",
            "DS_NOME_TRECHO",
        ],
    )
    st.success("Parâmetros de **atendimento** atualizados com sucesso.")


def insert_sat(ch_client):
    data = conn.query("SELECT * FROM sat", ttl=0)

    (new_version, creation_timestamp) = ch_client.command(
        "SELECT (MAX(CD_DEPLOY_ID) + 1) AS next_deploy_id, now64(3, 'UTC') FROM BD_PER.TB_PARAMETROS_SAT SETTINGS date_time_output_format = 'iso'"
    )
    creation_timestamp = datetime.datetime.fromisoformat(creation_timestamp)

    data["deploy_id"] = new_version
    data["deploy_timestamp"] = creation_timestamp
    data = data[
        [
            "cnpj",
            "tipo_interrup",
            "tempo_max_interrup",
            "pct_max_interrup",
            "deploy_id",
            "deploy_timestamp",
        ]
    ]
    ch_client.insert_df(
        "BD_PER.TB_PARAMETROS_SAT",
        data,
        column_names=[
            "NU_CNPJ",
            "CD_TIPO_INTERRUPCAO",
            "VL_TEMPO_MAX_INTERRUPCAO",
            "VL_PCT_MAX_INTERRUPCAO",
            "CD_DEPLOY_ID",
            "DT_DEPLOY_TIMESTAMP",
        ],
    )
    st.success("Parâmetros de **SAT** atualizados com sucesso.")


@st.dialog("ATENÇÃO: confirme as mudanças")
def confirm_action(action_functions, dataset_names):
    # juntando os nomes dos datasets a serem alterados
    names = ", ".join(dataset_names)

    # mensagem de aviso
    st.markdown(f"Você tem certeza que deseja alterar os parâmetros de **{names}**?")
    st.markdown(
        "Esta ação afetará todas as visualizações e análises dependentes destes parâmetros."
    )
    st.markdown(
        "Para **cancelar**, clique fora deste aviso, pressione a tecla `ESC` ou clique no ✖ no canto superior direito."
    )

    if st.button("Confirmar"):
        # só pegamos a conexão quando o usuário confima
        # a conexão é lenta e pesada, e colocar pra fora daqui
        # corre risco do Streamlit refazer a conexão
        # a cada refresh de estado do frontend

        try:
            ch_client().ping()
        except Exception as e:  # noqa: BLE001
            st.error(
                "Erro na conexão com o banco de dados.\n\nPor favor tente novamente mais tarde ou contate a equipe de suporte."
            )
            get_general_logger().error(
                f"{{event: 'db_connection_error', error: '{e!s}'}}"
            )

        for name, action in zip(dataset_names, action_functions):
            try:
                action(ch_client())
            except Exception as e:  # noqa: BLE001
                get_query_logger().error(
                    f"{{event: 'sync_error', dataset: '{name}', error: '{e!s}'}}"
                )
                st.error(f"Erro ao atualizar os parâmetros de **{name}**.")


st.title("Sincronização de dados")

st.markdown(
    "Selecione os parâmetros no gerenciador a serem sincronizados com as visualizações e análises."
)

checks = {
    "Radar": {
        "checkbox": st.checkbox("Radar"),
        "action": insert_radar,
        "dataset_name": "Radar",
    },
    "Pedágio": {
        "checkbox": st.checkbox("Pedágio"),
        "action": insert_pedagio,
        "dataset_name": "Pedágio",
    },
    "VIT": {
        "checkbox": st.checkbox("VIT"),
        "action": insert_vit,
        "dataset_name": "VIT",
    },
    "Atendimento": {
        "checkbox": st.checkbox("Atendimento"),
        "action": insert_atendimento,
        "dataset_name": "Atendimento",
    },
    "SAT": {
        "checkbox": st.checkbox("SAT"),
        "action": insert_sat,
        "dataset_name": "SAT",
    },
}


def main_sync():
    # pega os botões ativos
    active_checks = [value for _, value in checks.items() if value["checkbox"]]
    if len(active_checks) == 0:
        st.warning("Nenhum parâmetro selecionado.")
        return

    dataset_names = [d["dataset_name"] for d in active_checks]
    action_functions = [d["action"] for d in active_checks]

    confirm_action(action_functions, dataset_names)


if st.button("Sincronizar"):
    main_sync()
