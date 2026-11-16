from datetime import date

import pandas as pd
import streamlit as st

from client import ch_client
from spotfire import format_seconds, get_company_names


@st.cache_data(show_spinner=False)
def _all_evasoes(company_names: dict[str, str]) -> pd.DataFrame:
    client = ch_client()
    EvasoesAll = client.query_df(
        """
    SELECT
        NU_CNPJ,
        CD_PRACA_PEDAGIO AS CD_PRACA,
        raw.NO_PRACA_PEDAGIO AS NO_PRACA,
        DT_MES,
        SUM(QT_EVASOES) AS VL_SOMA_EVASOES,
        SUM(QT_CONTAGEM) AS QT_TOTAL_EVASOES,
        (SUM(QT_EVASOES) / SUM(QT_CONTAGEM)) AS VL_PCT_EVASOES
    FROM BD_ANALYTICS_SIR.MV_PEDAGIO_EVASOES_MES mv
    LEFT JOIN BD_RAW_SIR_ORIGEM.TB_PRACA_PEDAGIO raw
    ON mv.CD_PRACA_PEDAGIO = raw.CD_SEQ_PRACA_PEDAGIO
    GROUP BY NU_CNPJ, CD_PRACA, NO_PRACA, DT_MES
    """
    )
    EvasoesAll["NO_FANTASIA"] = EvasoesAll["NU_CNPJ"].map(company_names)
    return EvasoesAll


@st.cache_data(show_spinner=False, ttl=64800)
def pedagio_data_function_tables(
    date_range: tuple[date, date],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Função baseada na MainDataFunction da Análise de Pedágio do Spotfire.
    Os resultados importantes para o contexto desse gerador de relatórios são as variáveis, nessa ordem:
    - `ParamSummaryTable`
    - `EvasoesAll`
    - `Interruptions`

    Como os resultados são curtos, cache é viável.
    """

    TOTAL_STEPS = 5
    progress_bar = st.progress(0, text="Estabelecendo conexão com o banco de dados...")
    min_day, max_day = date_range
    min_day_str = min_day.strftime("%Y-%m-%d")
    max_day_str = max_day.strftime("%Y-%m-%d")
    client = ch_client()

    progress_bar.progress(
        1 / TOTAL_STEPS, text="Carregando nomes das concessionárias..."
    )
    company_names = get_company_names()

    progress_bar.progress(2 / TOTAL_STEPS, text="Calculando volume...")
    PedagioDataDays = client.query_df(f"""
    WITH
        toDate('{min_day}') AS start_date,
        toDate('{max_day}') AS end_date,

        date_range AS (
            SELECT start_date + number AS DT_DIA
            FROM system.numbers
            WHERE number <= dateDiff('day', start_date, end_date)
        ),

        companies AS (
            SELECT DISTINCT
                NU_CNPJ,
                CD_PRACA_PEDAGIO
            FROM BD_ANALYTICS_SIR.V_PEDAGIO_INFO
        ),

        counts AS (
            SELECT NU_CNPJ, CD_PRACA_PEDAGIO, DT_DIA, QT_CONTAGEM
            FROM BD_ANALYTICS_SIR.MV_PEDAGIO_CONTAGEM_DIARIA
            WHERE DT_DIA BETWEEN start_date AND end_date
        )
        
    SELECT
        c.NU_CNPJ AS NU_CNPJ,
        c.CD_PRACA_PEDAGIO AS CD_PRACA_PEDAGIO,
        d.DT_DIA AS DT_DIA,
        NULLIF(QT_CONTAGEM, 0) AS QT_CONTAGEM
    FROM companies c
    CROSS JOIN date_range d
    LEFT JOIN counts t
    ON
        c.CD_PRACA_PEDAGIO = t.CD_PRACA_PEDAGIO AND
        d.DT_DIA = t.DT_DIA
    ORDER BY c.NU_CNPJ, c.CD_PRACA_PEDAGIO, d.DT_DIA
    """)

    PedagioDataDays["NO_FANTASIA"] = PedagioDataDays["NU_CNPJ"].map(company_names)

    # INTERRUPÇÕES
    progress_bar.progress(3 / TOTAL_STEPS, text="Calculando interrupções...")
    query = """
    SELECT
        NU_CNPJ,
        CD_PRACA,
        NO_PRACA,
        greatest(DT_INSTANTE_ANTERIOR, DT_INICIO_MES) AS DT_INSTANTE_ANTERIOR,
        least(DT_INSTANTE, addSeconds(addMonths(DT_INICIO_MES, 1), -1)) AS DT_INSTANTE,
        dateDiff('second', greatest(DT_INSTANTE_ANTERIOR, DT_INICIO_MES), least(DT_INSTANTE, addSeconds(addMonths(DT_INICIO_MES, 1), -1))) AS VL_DELTA,
        VL_TOLERANCIA,
        formatDateTime(greatest(DT_INSTANTE_ANTERIOR, DT_INICIO_MES), '%Y-%m') AS DT_MES
    FROM (
        SELECT
            *,
            arrayJoin(
                arrayMap(
                    x -> addMonths(DT_PRIMEIRO_MES, x),
                    range(dateDiff('month', DT_PRIMEIRO_MES, toStartOfMonth(DT_INSTANTE)) + 1)
                )
            ) AS DT_INICIO_MES
        FROM (
            SELECT
                *,
                toStartOfMonth(DT_INSTANTE_ANTERIOR) AS DT_PRIMEIRO_MES
            FROM BD_ANALYTICS_SIR.MV_PEDAGIO_INTERRUPCOES
        )
    )
    WHERE greatest(DT_INSTANTE_ANTERIOR, DT_INICIO_MES) < least(DT_INSTANTE, addSeconds(addMonths(DT_INICIO_MES, 1), -1))
    ORDER BY NU_CNPJ, CD_PRACA, DT_INSTANTE_ANTERIOR
    """
    Interruptions = client.query_df(query)
    Interruptions["VL_DELTA_HORA"] = Interruptions["VL_DELTA"] / 60 / 60
    Interruptions["NO_FANTASIA"] = Interruptions["NU_CNPJ"].map(company_names)
    Interruptions["DS_DELTA_FORMATADO"] = Interruptions["VL_DELTA"].apply(
        format_seconds
    )

    int_equip_params = client.query_df(
        "SELECT * FROM BD_PER.TB_PARAMETROS_PEDAGIO WHERE CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_PEDAGIO) AND CD_TIPO_INTERRUPCAO = 1"
    )
    int_equip_params["VL_TEMPO_MAX_INTERRUPCAO"] = int_equip_params[
        "VL_TEMPO_MAX_INTERRUPCAO"
    ]

    IntEquip = Interruptions[
        Interruptions["NU_CNPJ"].isin(int_equip_params["NU_CNPJ"])
    ].copy()
    IntEquip["VL_TEMPO_MAX_INTERRUPCAO"] = IntEquip["NU_CNPJ"].map(
        int_equip_params.set_index("NU_CNPJ")["VL_TEMPO_MAX_INTERRUPCAO"]
    )
    IntEquip["VL_TEMPO_MAX_INTERRUPCAO"] = (
        IntEquip["VL_TEMPO_MAX_INTERRUPCAO"] * 60 * 60
    )
    IntEquip = IntEquip[IntEquip["VL_DELTA"] > IntEquip["VL_TEMPO_MAX_INTERRUPCAO"]]
    IntEquip["DS_TIPO"] = "Equipamento"

    params_code = {
        2: ["Sistema"],
        1: ["Equipamento"],
    }

    progress_bar.progress(
        4 / TOTAL_STEPS, text="Calculando cumprimento de parâmetros..."
    )
    ParamSummaryTable = PedagioDataDays.copy()
    ParamSummaryTable["DT_MES"] = (
        PedagioDataDays["DT_DIA"].dt.to_period("M").astype(str)
    )
    ParamSummaryTable = (
        ParamSummaryTable.groupby(["NU_CNPJ", "DT_MES"])
        .agg({"QT_CONTAGEM": "sum"})
        .reset_index()
    )

    # pegando os parametros para cada concessionaria
    params_con_all = client.query_df(
        "SELECT toString(NU_CNPJ) AS NU_CNPJ, CD_TIPO_INTERRUPCAO, VL_TEMPO_MAX_INTERRUPCAO AS VL_TEMPO_MAX_INTERRUPCAO FROM BD_PER.TB_PARAMETROS_PEDAGIO WHERE CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_PEDAGIO)"
    )

    ParamSummaryTable = ParamSummaryTable.merge(params_con_all, how="left")

    ParamSummaryTable["DS_TIPO"] = ParamSummaryTable["CD_TIPO_INTERRUPCAO"].map(
        params_code
    )
    ParamSummaryTable = ParamSummaryTable.explode("DS_TIPO").reset_index(drop=True)
    ParamSummaryTable = ParamSummaryTable.dropna()

    int_equip_summary = IntEquip.groupby(
        ["NU_CNPJ", "DT_MES", "VL_TEMPO_MAX_INTERRUPCAO", "DS_TIPO"], as_index=False
    ).size()
    int_equip_summary["ST_CUMPRIDO"] = int_equip_summary["size"] == 0
    int_equip_summary["VL_TEMPO_MAX_INTERRUPCAO"] = (
        int_equip_summary["VL_TEMPO_MAX_INTERRUPCAO"] / 60 / 60
    )
    int_equip_summary["VL_TEMPO_MAX_INTERRUPCAO"] = int_equip_summary[
        "VL_TEMPO_MAX_INTERRUPCAO"
    ].astype(str)
    int_equip_summary["VL_TEMPO_MAX_INTERRUPCAO"] = (
        "0 (" + int_equip_summary["VL_TEMPO_MAX_INTERRUPCAO"] + "h)"
    )
    int_equip_summary = int_equip_summary.rename(
        columns={"size": "VL_VALOR", "VL_TEMPO_MAX_INTERRUPCAO": "VL_VALOR_ESPERADO"}
    )

    all_summaries = pd.concat([int_equip_summary])

    ParamSummaryTable = ParamSummaryTable.merge(all_summaries, how="left")
    # se há dados, e "ST_CUMPRIDO" de Equipamento é NULL, então é porque não houve infrações
    ParamSummaryTable.loc[
        (ParamSummaryTable["DS_TIPO"] == "Equipamento")
        & (ParamSummaryTable["ST_CUMPRIDO"].isna())
        & (ParamSummaryTable["QT_CONTAGEM"] > 0),
        "ST_CUMPRIDO",
    ] = True
    ParamSummaryTable["ST_CUMPRIDO"] = ParamSummaryTable["ST_CUMPRIDO"].map(
        {True: "Sim", False: "Não"}
    )
    ParamSummaryTable["NO_FANTASIA"] = ParamSummaryTable["NU_CNPJ"].map(company_names)
    # VL_VALOR_ESPERADO is VL_VALOR_ESPERADO if not null, VL_TEMPO_MAX_INTERRUPCAO otherwise
    ParamSummaryTable["VL_TEMPO_MAX_INTERRUPCAO"] = ParamSummaryTable[
        "VL_TEMPO_MAX_INTERRUPCAO"
    ]["VL_VALOR_ESPERADO"] = ParamSummaryTable.apply(
        lambda row: (
            row["VL_VALOR_ESPERADO"]
            if pd.notna(row["VL_VALOR_ESPERADO"])
            else f"0 ({row['VL_TEMPO_MAX_INTERRUPCAO']}h)"
        ),
        axis=1,
    )
    # VL_VALOR is 0 if ST_CUMPRIDO, else VL_VALOR
    ParamSummaryTable["VL_VALOR"] = ParamSummaryTable.apply(
        lambda row: 0 if row["ST_CUMPRIDO"] == "Sim" else row["VL_VALOR"], axis=1
    )
    ParamSummaryTable = ParamSummaryTable.drop(
        columns=["QT_CONTAGEM", "CD_TIPO_INTERRUPCAO", "VL_TEMPO_MAX_INTERRUPCAO"]
    )

    # ADD LOCALIZAÇÃO
    PracaLocations = client.query_df(
        """
        SELECT
            CD_PRACA_PEDAGIO AS CD_PRACA,
            CG_LATITUDE,
            CG_LONGITUDE
        FROM
            BD_ANALYTICS_SIR.V_PEDAGIO_INFO"""
    )

    Interruptions = Interruptions.merge(PracaLocations, on="CD_PRACA", how="left")

    # EVASÕES
    progress_bar.progress(5 / TOTAL_STEPS, text="Calculando evasões...")
    EvasoesAll = _all_evasoes(company_names)
    EvasoesMerged = EvasoesAll.merge(PracaLocations, on="CD_PRACA", how="left")
    EvasoesFiltered = EvasoesMerged[
        (EvasoesMerged["DT_MES"] >= min_day.strftime("%Y-%m"))
        & (EvasoesMerged["DT_MES"] <= max_day.strftime("%Y-%m"))
    ].copy()

    Interruptions["NU_CNPJ"] = Interruptions["NU_CNPJ"].str.zfill(14)
    EvasoesFiltered["NU_CNPJ"] = EvasoesFiltered["NU_CNPJ"].str.zfill(14)

    progress_bar.empty()
    return ParamSummaryTable, EvasoesFiltered, Interruptions
