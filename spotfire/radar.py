import calendar
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from client import ch_client
from spotfire import format_seconds, get_company_names


@st.cache_data(show_spinner=False, ttl=64800)
def _all_anomalies(company_names: dict[str, str]) -> pd.DataFrame:
    client = ch_client()
    AnomAll = client.query_df("""
    SELECT
        NU_CNPJ,
        CD_RADAR,
        DT_MES,
        info.CG_LATITUDE,
        info.CG_LONGITUDE,
        info.NO_RADAR,
        avgMerge(VL_VELOCIDADE_MEDIA) AS VL_VELOCIDADE_MEDIA,
        minMerge(VL_VELOCIDADE_MINIMA) AS VL_VELOCIDADE_MINIMA,
        maxMerge(VL_VELOCIDADE_MAXIMA) AS VL_VELOCIDADE_MAXIMA,
        countIfMerge(QT_CONTAGEM_ACIMA_LIMITE) AS QT_CONTAGEM_ACIMA_LIMITE,
        countMerge(QT_CONTAGEM) AS QT_CONTAGEM
    FROM BD_ANALYTICS_SIR.MV_RADAR_VELOCIDADES rv
    INNER JOIN BD_ANALYTICS_SIR.V_RADAR_INFO info
    ON rv.CD_RADAR = info.CD_RADAR
    GROUP BY ALL
    """)
    AnomAll = AnomAll[
        (AnomAll["VL_VELOCIDADE_MEDIA"] < 20)
        | (AnomAll["VL_VELOCIDADE_MAXIMA"] > 200)
        | (AnomAll["VL_VELOCIDADE_MINIMA"] < 20)
    ]
    AnomAll["med_anom"] = AnomAll["VL_VELOCIDADE_MEDIA"] < 20
    AnomAll["NO_FANTASIA"] = AnomAll["NU_CNPJ"].map(company_names)
    return AnomAll


@st.cache_data(show_spinner=False, ttl=64800)
def radar_data_function_tables(
    date_range: tuple[date, date],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Função baseada na MainDataFunction da Análise de Radar do Spotfire.
    Os resultados importantes para o contexto desse gerador de relatórios são as variáveis, nessa ordem:
    - `ParamSummaryTable`
    - `AnomAll`
    - `Interruptions`

    Como os resultados são curtos, cache é viável.
    """
    TOTAL_STEPS = 6
    progress_bar = st.progress(0, text="Estabelecendo conexão com o banco de dados...")
    client = ch_client()
    min_day, max_day = date_range
    min_day_str = min_day.strftime("%Y-%m-%d")
    max_day_str = max_day.strftime("%Y-%m-%d")

    progress_bar.progress(1 / TOTAL_STEPS, text="Obtendo nomes das concessionárias...")
    company_names = get_company_names()

    progress_bar.progress(2 / TOTAL_STEPS, text="Calculando volume...")
    radar_data_days_sql = f"""
    WITH
        toDate('{min_day_str}') AS start_date,
        toDate('{max_day_str}') AS end_date,

        -- gerando as datas
        date_range AS (
            SELECT start_date + number AS DT_DIA
            FROM system.numbers
            WHERE number <= dateDiff('day', start_date, end_date)
        ),

        companies AS (
            SELECT DISTINCT NU_CNPJ AS NU_CNPJ
            FROM BD_PER.TB_PARAMETROS_CONCESSIONARIAS
        ),

        -- counts per company per date
        counts AS (
            SELECT NU_CNPJ, DT_DIA, SUM(QT_CONTAGEM) AS QT_CONTAGEM
            FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
            WHERE DT_DIA BETWEEN start_date AND end_date
            GROUP BY NU_CNPJ, DT_DIA
            ORDER BY NU_CNPJ, DT_DIA
        )

    SELECT
        c.NU_CNPJ AS NU_CNPJ,
        d.DT_DIA AS DT_DIA,
        nullIf(QT_CONTAGEM, 0) AS QT_CONTAGEM
    FROM companies c
    CROSS JOIN date_range d
    LEFT JOIN counts cnt
    ON c.NU_CNPJ = cnt.NU_CNPJ AND d.DT_DIA = cnt.DT_DIA
    """
    RadarDataDays = client.query_df(radar_data_days_sql)
    RadarDataDays["NU_CNPJ"] = RadarDataDays["NU_CNPJ"].astype(str)
    RadarDataDays["NO_FANTASIA"] = RadarDataDays["NU_CNPJ"].map(company_names)

    # posição dos radares que aparecem em cada mês
    EquipmentMonths = client.query_df("""
    SELECT DISTINCT
        NU_CNPJ,
        CD_RADAR,
        toStartOfMonth(DT_DIA) AS DT_MES,
        SUM(QT_CONTAGEM) AS QT_CONTAGEM
    FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
    GROUP BY NU_CNPJ, CD_RADAR, DT_MES
    """)
    EquipmentMonths["NO_FANTASIA"] = EquipmentMonths["NU_CNPJ"].map(company_names)

    # qualidade dos aparelhos
    QtdEquipMes = client.query_df("""
    SELECT
        NU_CNPJ,
        CD_RADAR,
        toStartOfMonth(DT_DIA) AS DT_MES,
        SUM(QT_CONTAGEM) AS QT_CONTAGEM
    FROM BD_ANALYTICS_SIR.MV_RADAR_CONTAGEM_DIA
    GROUP BY ALL
    ORDER BY NU_CNPJ, CD_RADAR, DT_MES
    """)

    QtdEquipAnomalos = QtdEquipMes[QtdEquipMes["QT_CONTAGEM"] < 1_000].copy()
    QtdEquipAnomalos["NO_FANTASIA"] = QtdEquipAnomalos["NU_CNPJ"].map(company_names)

    # INTERRUPÇÕES
    progress_bar.progress(3 / TOTAL_STEPS, text="Calculando interrupções...")

    query = """
    SELECT
        NU_CNPJ,
        CD_RADAR,
        NO_RADAR,
        greatest(DT_INSTANTE_ANTERIOR, month_start) AS DT_INSTANTE_ANTERIOR,
        least(DT_INSTANTE, addSeconds(addMonths(month_start, 1), -1)) AS DT_INSTANTE,
        dateDiff('second', greatest(DT_INSTANTE_ANTERIOR, month_start), least(DT_INSTANTE, addSeconds(addMonths(month_start, 1), -1))) AS delta,
        VL_TOLERANCIA,
        toStartOfMonth(greatest(DT_INSTANTE_ANTERIOR, month_start)) AS DT_MES
    FROM (
        SELECT
            *,
            arrayJoin(
                arrayMap(
                    x -> addMonths(start_month, x),
                    range(dateDiff('month', start_month, toStartOfMonth(DT_INSTANTE)) + 1)
                )
            ) AS month_start
        FROM (
            SELECT
                *,
                toStartOfMonth(DT_INSTANTE_ANTERIOR) AS start_month
            FROM BD_ANALYTICS_SIR.MV_RADAR_INTERRUPCOES
        )
    )
    WHERE greatest(DT_INSTANTE_ANTERIOR, month_start) < least(DT_INSTANTE, addSeconds(addMonths(month_start, 1), -1))
    ORDER BY NU_CNPJ, CD_RADAR, DT_INSTANTE_ANTERIOR
    """
    Interruptions: pd.DataFrame = client.query_df(query)
    Interruptions["delta_h"] = Interruptions["delta"] / 60 / 60
    Interruptions["NO_FANTASIA"] = Interruptions["NU_CNPJ"].map(company_names)
    Interruptions["delta_fmt"] = Interruptions["delta"].apply(format_seconds)

    progress_bar.progress(4 / TOTAL_STEPS, text="Obtendo parâmetros operacionais...")
    # EQUIPAMENTO
    int_equip_params = client.query_df("""SELECT *
    FROM BD_PER.TB_PARAMETROS_RADAR
    WHERE (
        CD_TIPO_INTERRUPCAO IN (2, 3, 5) AND
        CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_RADAR)
    )
    """)
    int_equip_params_cnpj = int_equip_params["NU_CNPJ"].unique()
    int_equip_params = int_equip_params.set_index("NU_CNPJ").to_dict(orient="index")
    int_equip_params = {
        k: v["VL_TEMPO_MAX_INTERRUPCAO"]
        for k, v in int_equip_params.items()
        if k is not None
    }

    IntEquip = Interruptions[
        (Interruptions["NU_CNPJ"].isin(int_equip_params_cnpj))
    ].copy()
    IntEquip["tempo_max"] = IntEquip["NU_CNPJ"].map(int_equip_params) * 60 * 60
    IntEquip = IntEquip[IntEquip["delta"] > IntEquip["tempo_max"]]
    IntEquip["delta"] = IntEquip["delta"].astype("Int64")
    IntEquip["VL_TOLERANCIA"] = IntEquip["VL_TOLERANCIA"].astype("Float64")
    IntEquip["tempo_max"] = IntEquip["tempo_max"].astype("Int64")
    IntEquip["tipo"] = "Equipamento"

    # SISTEMA
    int_sis_params = client.query_df("""
    SELECT *
    FROM BD_PER.TB_PARAMETROS_RADAR
    WHERE
        CD_TIPO_INTERRUPCAO IN (1, 3, 4, 5) AND
        CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_RADAR)
    """)
    int_sis_params_cnpj = int_sis_params["NU_CNPJ"].unique()
    int_sis_params = int_sis_params.set_index("NU_CNPJ").to_dict(orient="index")
    int_sis_params = {
        k: v["VL_TEMPO_MAX_INTERRUPCAO"]
        for k, v in int_sis_params.items()
        if k is not None
    }

    IntSis = Interruptions[(Interruptions["NU_CNPJ"].isin(int_sis_params_cnpj))].copy()
    IntSis = IntSis[["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES", "delta"]]
    IntSis = IntSis.groupby(
        ["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES"], as_index=False
    ).agg(mean_delta=("delta", "mean"))
    IntSis = IntSis.groupby(["NU_CNPJ", "DT_MES"], as_index=False).agg(
        mean_mean_delta=("mean_delta", "mean")
    )
    IntSis["tempo_max"] = IntSis["NU_CNPJ"].map(int_sis_params) * 60 * 60
    IntSis["tipo"] = "Sistema"

    # SISTEMA %
    int_sisp_params = client.query_df("""SELECT *
    FROM BD_PER.TB_PARAMETROS_RADAR
    WHERE
        CD_TIPO_INTERRUPCAO IN (4, 5) AND
        CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_RADAR)
    """)
    int_sisp_params_cnpj = int_sisp_params["NU_CNPJ"].unique()
    int_sisp_params = int_sisp_params.set_index("NU_CNPJ").to_dict(orient="index")
    int_sisp_params = {
        k: v["VL_PCT_MAX_INTERRUPCAO"]
        for k, v in int_sisp_params.items()
        if k is not None
    }

    IntSisPor = Interruptions[
        (Interruptions["NU_CNPJ"].isin(int_sisp_params_cnpj))
    ].copy()
    IntSisPor = IntSisPor[["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES", "delta"]]
    IntSisPor = IntSisPor.groupby(
        ["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES"], as_index=False
    ).agg(sum_delta=("delta", "sum"))
    IntSisPor["year"] = IntSisPor["DT_MES"].dt.year
    IntSisPor["month_num"] = IntSisPor["DT_MES"].dt.month
    IntSisPor["days_in_month"] = IntSisPor.apply(
        lambda row: calendar.monthrange(row["year"], row["month_num"])[1], axis=1
    )
    IntSisPor["seconds_in_month"] = IntSisPor["days_in_month"] * 24 * 60 * 60
    IntSisPor["p"] = 1 - (IntSisPor["sum_delta"] / IntSisPor["seconds_in_month"])
    IntSisPor = IntSisPor[["NU_CNPJ", "CD_RADAR", "DT_MES", "p"]]
    IntSisPor = (
        IntSisPor.groupby(["NU_CNPJ", "DT_MES"], as_index=False).agg(
            mean_p=("p", "mean")
        )
    ).sort_values(by="DT_MES")
    IntSisPor["pct_min"] = IntSisPor["NU_CNPJ"].map(int_sisp_params) / 100.0

    IntSisPor["mean_p"] = np.round(IntSisPor["mean_p"], 4) * 100
    IntSisPor["pct_min"] = IntSisPor["pct_min"] * 100
    IntSisPor["tipo"] = "Sistema (%)"

    progress_bar.progress(
        5 / TOTAL_STEPS, text="Calculando cumprimento de parâmetros..."
    )
    # RESUMO
    params_code = {
        1: ["Sistema"],
        2: ["Equipamento"],
        3: ["Sistema", "Equipamento"],
        4: ["Sistema", "Sistema (%)"],
        5: ["Sistema", "Sistema (%)", "Equipamento"],
    }

    ParamSummaryTable = RadarDataDays.copy()
    ParamSummaryTable["NU_CNPJ"] = ParamSummaryTable["NU_CNPJ"].astype(str)
    ParamSummaryTable["DT_MES_str"] = (
        RadarDataDays["DT_DIA"].dt.to_period("M").astype(str)
    )
    ParamSummaryTable = (
        ParamSummaryTable.rename(columns={"QT_CONTAGEM": "count"})
        .groupby(["NU_CNPJ", "DT_MES_str"])
        .agg({"count": "sum"})
        .reset_index()
    )

    # pegando os parametros para cada concessionaria
    params_con_all = client.query_df(
        "SELECT NU_CNPJ, CD_TIPO_INTERRUPCAO FROM BD_PER.TB_PARAMETROS_RADAR WHERE CD_DEPLOY_ID = (SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_RADAR)"
    )
    ParamSummaryTable = ParamSummaryTable.merge(params_con_all, how="left")

    ParamSummaryTable["tipo"] = ParamSummaryTable["CD_TIPO_INTERRUPCAO"].map(
        params_code
    )
    ParamSummaryTable = ParamSummaryTable.explode("tipo").reset_index(drop=True)

    # RESUMO EQUIPAMENTO
    int_equip_summary = IntEquip.groupby(
        ["NU_CNPJ", "DT_MES", "tempo_max", "tipo"], as_index=False
    ).size()
    int_equip_summary["cumpriu"] = int_equip_summary["size"] == 0
    int_equip_summary["tempo_max"] = (
        (int_equip_summary["tempo_max"] / 60 / 60).astype(int).astype(str)
    )
    int_equip_summary["tempo_max"] = "0 (" + int_equip_summary["tempo_max"] + "h)"
    int_equip_summary = int_equip_summary.rename(
        columns={"size": "val", "tempo_max": "val_esp"}
    )

    # RESUMO SISTEMA
    int_sis_summary = IntSis.rename(
        columns={"mean_mean_delta": "val", "tempo_max": "val_esp"}
    )
    int_sis_summary["cumpriu"] = int_sis_summary["val"] <= int_sis_summary["val_esp"]
    int_sis_summary["val_esp"] = (int_sis_summary["val_esp"] / 60 / 60).astype(int)
    int_sis_summary["val"] = (
        np.round(int_sis_summary["val"]).astype(int).apply(format_seconds)
    )
    int_sis_summary["val_esp"] = int_sis_summary["val_esp"].astype(str) + "h"

    # RESUMO SISTEMA %
    int_sis_por_summary = IntSisPor.rename(
        columns={"mean_p": "val", "pct_min": "val_esp"}
    )
    int_sis_por_summary["cumpriu"] = (
        int_sis_por_summary["val"] >= int_sis_por_summary["val_esp"]
    )
    int_sis_por_summary["val"] = int_sis_por_summary["val"].astype(str) + "%"
    int_sis_por_summary["val_esp"] = int_sis_por_summary["val_esp"].astype(str) + "%"

    # JUNTANDO TUDO NA SUMMARY TABLE
    int_equip_summary["val"] = int_equip_summary["val"].astype(str)
    int_sis_summary["val"] = int_sis_summary["val"].astype(str)
    int_sis_por_summary["val"] = int_sis_por_summary["val"].astype(str)
    all_summaries = pd.concat([int_equip_summary, int_sis_summary, int_sis_por_summary])
    all_summaries["DT_MES_str"] = all_summaries["DT_MES"].dt.strftime("%Y-%m")

    ParamSummaryTable = ParamSummaryTable.merge(
        all_summaries, how="left", on=["NU_CNPJ", "DT_MES_str", "tipo"]
    )
    # se há dados, e "cumpriu" de Equipamento é NULL, então é porque não houve infrações
    ParamSummaryTable.loc[
        (ParamSummaryTable["tipo"] == "Equipamento")
        & (ParamSummaryTable["cumpriu"].isna())
        & (ParamSummaryTable["count"] > 0),
        "cumpriu",
    ] = True
    ParamSummaryTable["cumpriu"] = ParamSummaryTable["cumpriu"].map(
        {True: "Sim", False: "Não"}
    )
    # para quaisquer outros casos, se cumpriu é NULL, é porque faltam dados
    ParamSummaryTable = ParamSummaryTable.fillna("-")
    ParamSummaryTable = ParamSummaryTable.drop(columns=["count", "CD_TIPO_INTERRUPCAO"])
    ParamSummaryTable["NO_FANTASIA"] = ParamSummaryTable["NU_CNPJ"].map(company_names)

    IntSisPorAll = Interruptions.copy()
    IntSisPorAll = IntSisPorAll[["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES", "delta"]]
    IntSisPorAll = IntSisPorAll.groupby(
        ["NU_CNPJ", "CD_RADAR", "NO_RADAR", "DT_MES"], as_index=False
    ).agg(sum_delta=("delta", "sum"))
    IntSisPorAll["year"] = IntSisPorAll["DT_MES"].dt.year
    IntSisPorAll["month_num"] = IntSisPorAll["DT_MES"].dt.month
    IntSisPorAll["days_in_month"] = IntSisPorAll.apply(
        lambda row: calendar.monthrange(row["year"], row["month_num"])[1], axis=1
    )
    IntSisPorAll["seconds_in_month"] = IntSisPorAll["days_in_month"] * 24 * 60 * 60
    IntSisPorAll["p"] = 1 - (
        IntSisPorAll["sum_delta"] / IntSisPorAll["seconds_in_month"]
    )
    IntSisPorAll = IntSisPorAll[["NU_CNPJ", "CD_RADAR", "DT_MES", "p"]]
    IntSisPorAll = (
        IntSisPorAll.groupby(["NU_CNPJ", "DT_MES"], as_index=False).agg(
            mean_p=("p", "mean")
        )
    ).sort_values(by="DT_MES")
    IntSisPorAll["pct_min"] = IntSisPorAll["NU_CNPJ"].map(int_sisp_params) / 100.0
    IntSisPorAll["mean_p"] = np.round(IntSisPorAll["mean_p"], 4)
    IntSisPorAll["pct_min"] = (IntSisPorAll["pct_min"]).astype("Float64")
    IntSisPorAll["tipo"] = "Sistema (%)"
    IntSisPorAll["is_param"] = IntSisPorAll["pct_min"].notna()
    IntSisPorAll["cumpriu"] = IntSisPorAll["mean_p"] >= IntSisPorAll["pct_min"]
    IntSisPorAll["NO_FANTASIA"] = IntSisPorAll["NU_CNPJ"].map(company_names)

    # LOCALIZAÇÃO
    RadarLocations = client.query_df(
        """
        SELECT
            CD_RADAR,
            CG_LATITUDE,
            CG_LONGITUDE
        FROM BD_ANALYTICS_SIR.V_RADAR_INFO"""
    )
    Interruptions = Interruptions.merge(RadarLocations, on="CD_RADAR", how="left")

    # ANOMALIAS
    progress_bar.progress(6 / TOTAL_STEPS, text="Calculando anomalias...")
    AnomAll = _all_anomalies(company_names)
    AnomFiltered = AnomAll[
        (AnomAll["DT_MES"] >= min_day.strftime("%Y-%m"))
        & (AnomAll["DT_MES"] <= max_day.strftime("%Y-%m"))
    ].copy()

    progress_bar.empty()
    return ParamSummaryTable, AnomFiltered, Interruptions
