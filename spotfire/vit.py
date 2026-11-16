from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from client import ch_client
from spotfire import get_company_names


@st.cache_data(show_spinner=False, ttl=64800)
def vit_data_function_tables(
    date_range: tuple[date, date],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Função baseada na MainDataFunction da Análise de VIT do Spotfire.
    Os resultados importantes para o contexto desse gerador de relatórios são as variáveis, nessa ordem:
    - `Atrasos`
    - `FullSummary`
    """

    TOTAL_STEPS = 5
    progress_bar = st.progress(0, text="Estabelecendo conexão com o banco de dados...")
    client = ch_client()
    min_day, max_day = date_range
    min_day_str = min_day.strftime("%Y-%m-%d")
    max_day_str = max_day.strftime("%Y-%m-%d")

    progress_bar.progress(
        1 / TOTAL_STEPS, text="Carregando nomes das concessionárias..."
    )
    company_names = get_company_names()

    # Quantidade de dados
    progress_bar.progress(2 / TOTAL_STEPS, text="Carregando dados geográficos...")
    pedagio_coords = client.query_df(
        "SELECT NU_CNPJ, CD_PRACA_PEDAGIO AS CD_PONTO, CG_LATITUDE, CG_LONGITUDE FROM BD_ANALYTICS_SIR.V_PEDAGIO_INFO"
    )
    pedagio_coords["DS_TIPO_PONTO"] = "Pedágio"
    radar_coords = client.query_df(
        "SELECT NU_CNPJ, CD_RADAR AS CD_PONTO, CG_LATITUDE, CG_LONGITUDE FROM BD_ANALYTICS_SIR.V_RADAR_INFO"
    )
    radar_coords["DS_TIPO_PONTO"] = "Radar"
    all_coords = pd.concat([pedagio_coords, radar_coords])

    # ANÁLISE DOS PARÂMETROS OPERACIONAIS
    # DADOS BASE

    progress_bar.progress(3 / TOTAL_STEPS, text="Carregando dados de distância...")
    vit_deltas_dist = client.query_df(
        f"""
    SELECT * FROM (
        SELECT
            NU_CNPJ,
            DS_PLACA,
            formatDateTime(toStartOfMonth(DT_PASSAGEM_ANTERIOR), '%Y-%m') AS DT_MES,
            DT_PASSAGEM_ANTERIOR AS DT_INSTANTE_ANTERIOR,
            DT_PASSAGEM AS DT_INSTANTE,
            (VL_INTERVALO * 60)::Int64 AS VL_DELTA, -- Min to Sec
            -- dados do ponto
            DS_TIPO_PONTO_ANTERIOR,
            NO_PONTO_ANTERIOR,
            DS_TIPO_PONTO,
            NO_PONTO,
            -- dados de espaço
            CD_RODOVIA_PONTO_ANTERIOR,
            KM_PONTO_ANTERIOR,
            CD_RODOVIA_PONTO,
            KM_PONTO,
            VL_DISTANCIA_KM
        FROM (
            SELECT *
            FROM BD_ANALYTICS_SIR.MV_VIT_INTERVALOS_VEICULOS
            WHERE DT_PASSAGEM BETWEEN toDate('{min_day_str}') AND toDate('{max_day_str}')
        )
    ) WHERE VL_DELTA != 0 AND VL_DISTANCIA_KM != 0 AND CD_RODOVIA_PONTO_ANTERIOR = CD_RODOVIA_PONTO
    """
    )

    vit_deltas_dist["VL_DELTA_HORAS"] = vit_deltas_dist["VL_DELTA"] / 3_600

    vit_deltas_dist["VL_VELOCIDADE_MEDIA"] = (
        vit_deltas_dist["VL_DISTANCIA_KM"] / vit_deltas_dist["VL_DELTA_HORAS"]
    )

    progress_bar.progress(
        4 / TOTAL_STEPS, text="Calculando cumprimento de parâmetros..."
    )
    # CALCULANDO ATRASOS E VELOCIDADES

    # ATRASOS/IT
    it_params = client.query_df(
        "SELECT NU_CNPJ, VL_INTERVALO FROM BD_PER.TB_PARAMETROS_VIT WHERE CD_DEPLOY_ID=(SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_VIT) AND VL_INTERVALO IS NOT NULL"
    )
    Atrasos = client.query_df(f"""
    SELECT
        NU_CNPJ,
        DS_TIPO_PONTO,
        CD_PONTO,
        NO_PONTO,
        CD_SENTIDO,
        NO_SENTIDO,
        DT_PASSAGEM_ANTERIOR AS DT_INSTANTE_ANTERIOR,
        DT_PASSAGEM AS DT_INSTANTE,
        DS_PLACA_ANTERIOR,
        DS_PLACA as DS_PLACA,
        (60 * VL_INTERVALO)::Int64 AS VL_DELTA -- Min To Sec
    FROM (SELECT * FROM BD_ANALYTICS_SIR.MV_VIT_ATRASOS WHERE DT_PASSAGEM BETWEEN toDate('{min_day_str}') AND toDate('{max_day_str}'))
    """)
    Atrasos = Atrasos.merge(it_params, how="left", on="NU_CNPJ")
    Atrasos["VL_INTERVALO_SEGUNDOS"] = Atrasos["VL_INTERVALO"] * 60
    # manteremos apenas os atrasos
    # concessionárias sem atrasos serão tratadas na montagem da tabela resumo agregada
    Atrasos = Atrasos[Atrasos["VL_DELTA"] > Atrasos["VL_INTERVALO_SEGUNDOS"]]
    Atrasos["VL_ATRASO_SEGUNDOS"] = (
        Atrasos["VL_DELTA"] - Atrasos["VL_INTERVALO_SEGUNDOS"]
    ).clip(lower=0)  # nem precisaria do clip
    Atrasos["DT_MES"] = Atrasos["DT_INSTANTE_ANTERIOR"].dt.strftime("%Y-%m")

    Atrasos["VL_DELTA"] = Atrasos["VL_DELTA"].astype("Int64")
    Atrasos["VL_INTERVALO"] = Atrasos["VL_INTERVALO"].astype("Int64")
    Atrasos["VL_INTERVALO_SEGUNDOS"] = Atrasos["VL_INTERVALO_SEGUNDOS"].astype("Int64")
    Atrasos["VL_ATRASO_SEGUNDOS"] = Atrasos["VL_ATRASO_SEGUNDOS"].astype("Int64")
    Atrasos["atraso_mins"] = Atrasos["VL_ATRASO_SEGUNDOS"] / 60
    Atrasos["fantasia"] = Atrasos["NU_CNPJ"].map(company_names)
    Atrasos = Atrasos.merge(all_coords, how="left", on=["NU_CNPJ", "DS_TIPO_PONTO"])

    # SOMA 4
    s_atrasos = (
        Atrasos[
            [
                "NU_CNPJ",
                "DT_MES",
                "DS_TIPO_PONTO",
                "NO_PONTO",
                "CD_SENTIDO",
                "NO_SENTIDO",
                "DT_INSTANTE_ANTERIOR",
                "VL_ATRASO_SEGUNDOS",
            ]
        ]
        .sort_values(
            by=[
                "NU_CNPJ",
                "DT_MES",
                "DS_TIPO_PONTO",
                "NO_PONTO",
                "CD_SENTIDO",
                "NO_SENTIDO",
                "DT_INSTANTE_ANTERIOR",
            ]
        )
        .reset_index(drop=True)
        .copy()
    )

    s_atrasos["row_in_group"] = s_atrasos.groupby(
        [
            "NU_CNPJ",
            "DT_MES",
            "DS_TIPO_PONTO",
            "NO_PONTO",
            "CD_SENTIDO",
            "NO_SENTIDO",
        ]
    ).cumcount()

    s_atrasos["batch_id"] = s_atrasos["row_in_group"] // 4

    batch_sizes = s_atrasos.groupby(
        [
            "NU_CNPJ",
            "DT_MES",
            "DS_TIPO_PONTO",
            "NO_PONTO",
            "CD_SENTIDO",
            "NO_SENTIDO",
            "batch_id",
        ]
    )["VL_ATRASO_SEGUNDOS"].transform("count")

    s_atrasos = s_atrasos[batch_sizes == 4]

    SumAtrasos = (
        s_atrasos.groupby(
            [
                "NU_CNPJ",
                "DT_MES",
                "DS_TIPO_PONTO",
                "NO_PONTO",
                "CD_SENTIDO",
                "NO_SENTIDO",
                "batch_id",
            ]
        )
        .agg(VL_SOMA_ATRASOS_SEGUNDOS=("VL_ATRASO_SEGUNDOS", "sum"))
        .reset_index()
    )

    sum_params = client.query_df(
        "SELECT NU_CNPJ, VL_SOMA_QUATRO_ATRASOS FROM BD_PER.TB_PARAMETROS_VIT WHERE CD_DEPLOY_ID=(SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_VIT) AND VL_SOMA_QUATRO_ATRASOS IS NOT NULL"
    )

    SumAtrasos = SumAtrasos.merge(sum_params, how="left", on="NU_CNPJ")
    SumAtrasos["VL_SOMA_QUATRO_ATRASOS_SEGUNDOS"] = (
        SumAtrasos["VL_SOMA_QUATRO_ATRASOS"] * 60
    )

    # só os descumprimentos
    SumAtrasos = SumAtrasos[
        SumAtrasos["VL_SOMA_ATRASOS_SEGUNDOS"]
        > SumAtrasos["VL_SOMA_QUATRO_ATRASOS_SEGUNDOS"]
    ]

    # VELOCIDADE MÉDIA DOS VEÍCULOS
    VelMed = vit_deltas_dist[
        ["NU_CNPJ", "DT_MES", "DT_INSTANTE_ANTERIOR", "DS_PLACA", "VL_VELOCIDADE_MEDIA"]
    ].copy()
    VelMed["DT_MES"] = VelMed["DT_INSTANTE_ANTERIOR"].dt.strftime("%Y-%m")
    VelMed = VelMed.drop(columns=["DT_INSTANTE_ANTERIOR"])
    VelMed = (
        VelMed.groupby(["NU_CNPJ", "DS_PLACA", "DT_MES"])
        .agg({"VL_VELOCIDADE_MEDIA": "mean"})
        .reset_index()
    )

    # TABELA RESUMO BASE
    min_ts = pd.to_datetime(min_day).replace(day=1)
    max_ts = pd.to_datetime(max_day).replace(day=1)

    month_span = (
        pd.date_range(start=min_ts, end=max_ts, freq="MS").strftime("%Y-%m").tolist()
    )

    BaseTable = client.query_df(
        "SELECT DISTINCT NU_CNPJ FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS"
    )
    months_df = pd.DataFrame({"DT_MES": month_span})

    BaseTable = (
        BaseTable.assign(key=1)
        .merge(months_df.assign(key=1), on="key")
        .drop("key", axis=1)
    )

    BaseTable = BaseTable.merge(
        client.query_df(
            "SELECT NU_CNPJ, formatDateTime(toStartOfMonth(DT_INSTANTE), '%Y-%m') AS DT_MES, COUNT(*) as QT_CONTAGEM FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS GROUP BY NU_CNPJ, DT_MES"
        ),
        how="left",
        on=["NU_CNPJ", "DT_MES"],
    )

    BaseTable = BaseTable.fillna(0)

    def cumpriu(row):
        if (row["VL_VALOR"] > 0) and (row["QT_CONTAGEM"] > 0):
            return "Não"
        elif row["QT_CONTAGEM"] == 0:
            return "-"
        return "Sim"

    # RESUMO: IT
    AtrasosGrouped = (
        Atrasos.groupby(["NU_CNPJ", "DT_MES"]).size().reset_index(name="QT_ATRASOS")
    )
    AtrasosSummary = BaseTable.copy()
    AtrasosSummary = AtrasosSummary.merge(
        AtrasosGrouped, how="left", on=["NU_CNPJ", "DT_MES"]
    )
    AtrasosSummary = AtrasosSummary.fillna(0)
    AtrasosSummary = AtrasosSummary.merge(it_params, on="NU_CNPJ")
    AtrasosSummary["VL_VALOR_ESPERADO"] = (
        "0 (" + AtrasosSummary["VL_INTERVALO"].astype(str) + "min)"
    )
    AtrasosSummary = AtrasosSummary.rename(columns={"QT_ATRASOS": "VL_VALOR"})
    AtrasosSummary = AtrasosSummary.drop(columns=["VL_INTERVALO"])
    AtrasosSummary["cumpriu"] = AtrasosSummary.apply(cumpriu, axis=1)
    AtrasosSummary["tipo"] = "IT"

    # RESUMO: SOMA4
    SomaGrouped = (
        SumAtrasos.groupby(["NU_CNPJ", "DT_MES"])
        .size()
        .reset_index(name="count_b_acima")
    )

    SomaSummary = BaseTable.copy()
    SomaSummary = SomaSummary.merge(SomaGrouped, how="left", on=["NU_CNPJ", "DT_MES"])
    SomaSummary = SomaSummary.fillna(0)
    SomaSummary["count_b_acima"] = SomaSummary["count_b_acima"].astype("Int64")
    SomaSummary = SomaSummary.merge(sum_params, on="NU_CNPJ")
    SomaSummary["VL_VALOR_ESPERADO"] = (
        "0 (" + SomaSummary["VL_SOMA_QUATRO_ATRASOS"].astype(str) + "min)"
    )
    SomaSummary = SomaSummary.rename(columns={"count_b_acima": "VL_VALOR"})
    SomaSummary = SomaSummary.drop(columns=["VL_SOMA_QUATRO_ATRASOS"])
    SomaSummary["cumpriu"] = SomaSummary.apply(cumpriu, axis=1)
    SomaSummary["tipo"] = "Σ4"

    # RESUMO: VMÉD
    vmed_params = client.query_df(
        "SELECT NU_CNPJ, VL_VELOCIDADE_MEDIA FROM BD_PER.TB_PARAMETROS_VIT WHERE CD_DEPLOY_ID=(SELECT MAX(CD_DEPLOY_ID) FROM BD_PER.TB_PARAMETROS_VIT) AND VL_VELOCIDADE_MEDIA IS NOT NULL"
    )
    vmed_params = vmed_params.dropna().reset_index(drop=True)
    VMedGrouped = (
        VelMed.groupby(["NU_CNPJ", "DT_MES"])["VL_VELOCIDADE_MEDIA"]
        .mean()
        .reset_index()
    )

    def cumpriu_vel(row):
        vmin = row["VL_VELOCIDADE_MEDIA_y"] - 10
        vmax = row["VL_VELOCIDADE_MEDIA_y"] + 10
        v = row["VL_VALOR"]

        if (vmin <= v <= vmax) and (row["QT_CONTAGEM"] > 0):
            return "Sim"
        elif row["QT_CONTAGEM"] == 0:
            return "-"
        return "Não"

    VMedSummary = BaseTable.copy()
    VMedSummary = VMedSummary.merge(VMedGrouped, how="left", on=["NU_CNPJ", "DT_MES"])
    VMedSummary = VMedSummary.fillna(0)
    VMedSummary = VMedSummary.merge(vmed_params, on="NU_CNPJ")
    VMedSummary["VL_VALOR_ESPERADO"] = (
        VMedSummary["VL_VELOCIDADE_MEDIA_y"].astype(str) + " ± 10 km/h"
    )
    VMedSummary = VMedSummary.rename(columns={"VL_VELOCIDADE_MEDIA_x": "VL_VALOR"})
    VMedSummary["ST_CUMPRIMENTO"] = VMedSummary.apply(cumpriu_vel, axis=1)
    VMedSummary["VL_VALOR"] = np.round(VMedSummary["VL_VALOR"], 2)
    VMedSummary = VMedSummary.drop(columns=["VL_VELOCIDADE_MEDIA_y"])
    VMedSummary["tipo"] = "VMéd"

    # TABELA FINAL
    progress_bar.progress(5 / TOTAL_STEPS, text="Finalizando cálculos...")
    AtrasosSummary["VL_VALOR"] = AtrasosSummary["VL_VALOR"].astype(str)
    SomaSummary["VL_VALOR"] = SomaSummary["VL_VALOR"].astype(str)
    VMedSummary["VL_VALOR"] = VMedSummary["VL_VALOR"].astype(str)

    FullSummary = pd.concat([AtrasosSummary, SomaSummary, VMedSummary])
    FullSummary["NO_FANTASIA"] = FullSummary["NU_CNPJ"].map(company_names)

    # SAÍDA DA VMÉD PARA CÁLCULOS
    VelMedOut = VelMed.merge(vmed_params, on="NU_CNPJ").drop(
        columns=["VL_VELOCIDADE_MEDIA_x"]
    )
    VelMedOut["NO_FANTASIA"] = VelMedOut["NU_CNPJ"].map(company_names)

    # FILTRO GERAL
    TodosMeses = client.query_df(
        "SELECT DISTINCT formatDateTime(DT_INSTANTE, '%Y-%m') AS DT_MES FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS"
    )

    TodasConcessionarias = client.query_df(
        """
    SELECT NU_CNPJ, p.NO_FANTASIA FROM
    (SELECT DISTINCT NU_CNPJ FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS) v
    LEFT JOIN BD_PER.TB_PARAMETROS_CONCESSIONARIAS p
    ON p.NU_CNPJ = v.NU_CNPJ
    """
    )

    TodosMeses["_key"] = 1
    TodasConcessionarias["_key"] = 1

    TodasConcessionarias = pd.merge(TodosMeses, TodasConcessionarias, on="_key").drop(
        "_key", axis=1
    )

    FullSummary["NU_CNPJ"] = FullSummary["NU_CNPJ"].astype(str)
    FullSummary["VL_VALOR"] = FullSummary["VL_VALOR"].astype(float).round().astype(int)
    FullSummary = FullSummary.drop(columns=["QT_CONTAGEM", "NO_FANTASIA"])
    Atrasos["NU_CNPJ"] = Atrasos["NU_CNPJ"].astype(str)
    progress_bar.empty()
    return Atrasos, FullSummary
