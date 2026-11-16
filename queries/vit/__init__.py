from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Final, TypedDict

import numpy as np
import pandas as pd
import streamlit as st

from client import ch_client
from spotfire.vit import vit_data_function_tables


class VitQueries(TypedDict):
    get_total_count: Path
    """
    :param cnpj (string)
    :return : DataFrame["QT_CONTAGEM" (UInt64)]
    """


AVAILABLE_VIT_QUERIES: Final[VitQueries] = {
    "get_total_count": Path("queries", "vit", "get_total_count.sql"),
}


@st.cache_data(show_spinner=False)
def load_vit_data():
    loaded_client = ch_client()
    genericas = loaded_client.query_df(
        "SELECT DS_PLACA FROM BD_RAW_INTERNO.TB_PLACAS_GENERICAS"
    )["DS_PLACA"].tolist()
    Veiculos = loaded_client.query_df("SELECT * FROM BD_ANALYTICS_SIR.V_VIT_CADASTRO v")
    Veiculos = Veiculos.drop(columns="NO_FANTASIA")
    Veiculos = Veiculos[~Veiculos["DS_PLACA"].isin(genericas)]

    # Contagens gerais
    CountsGlobal = Veiculos.groupby("NU_CNPJ").size().reset_index(name="QT_CADASTRADO")
    count_per = loaded_client.query_df(
        "SELECT * FROM BD_ANALYTICS_SIR.V_QUANTIDADE_VITS"
    )
    count_per = count_per.drop(columns=["NO_FANTASIA"])
    CountsGlobal = CountsGlobal.merge(count_per, how="left", on="NU_CNPJ")
    count_geral = loaded_client.query_df(
        "SELECT NU_CNPJ, COUNT(DISTINCT DS_PLACA) AS QT_VISTO FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS GROUP BY NU_CNPJ"
    )
    CountsGlobal = CountsGlobal.merge(count_geral, on="NU_CNPJ")

    return Veiculos, CountsGlobal, count_per


def get_vehicle_counts(cnpj: str):
    _, CountsGlobal, count_per = load_vit_data()
    count_per_cnpj = count_per.loc[count_per["NU_CNPJ"] == cnpj, "QT_VIT"]
    CountsGlobal_cnpj = CountsGlobal.loc[CountsGlobal["NU_CNPJ"] == cnpj]
    qtd_min = 0 if (len(count_per_cnpj) == 0) else count_per_cnpj.values[0]
    qtd_cadastro = (
        0
        if (len(CountsGlobal_cnpj) == 0)
        else CountsGlobal_cnpj["QT_CADASTRADO"].values[0]
    )
    qtd_visto = (
        0 if (len(CountsGlobal_cnpj) == 0) else CountsGlobal_cnpj["QT_VISTO"].values[0]
    )
    return qtd_min, qtd_cadastro, qtd_visto


def get_dates(cnpj):
    loaded_client = ch_client()
    VitDates = loaded_client.query_df(
        "SELECT NU_CNPJ, toDate(min(DT_INSTANTE)) AS start_date, toDate(max(DT_INSTANTE)) AS end_date FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS GROUP BY NU_CNPJ"
    )
    start_date = VitDates.loc[VitDates["cnpj"] == cnpj, "start_date"].values[0]
    end_date = VitDates.loc[VitDates["cnpj"] == cnpj, "end_date"].values[0]

    # format as DD/MM/YYYY
    start_date = pd.to_datetime(start_date).strftime("%d/%m/%Y")
    end_date = pd.to_datetime(end_date).strftime("%d/%m/%Y")

    return start_date, end_date


def get_daily_data(cnpj: str, min_day: str, max_day: str):
    # Dados diários
    loaded_client = ch_client()
    VitDataDays = loaded_client.query_df(f"""
    WITH
        toDate('{min_day}') AS DT_DATA_INICIO,
        toDate('{max_day}') AS DT_DATA_FIM,

        date_range AS (
            SELECT DT_DATA_INICIO + number AS DT_DIA
            FROM system.numbers
            WHERE number <= dateDiff('day', DT_DATA_INICIO, DT_DATA_FIM)
        ),

        companies AS (
            SELECT DISTINCT NU_CNPJ
            FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
            WHERE NU_CNPJ = '{cnpj}'
        ),

        -- counts per company per date
        counts AS (
            SELECT NU_CNPJ, toDate(DT_INSTANTE) AS DT_DIA, COUNT(DISTINCT DS_PLACA) AS QT_CONTAGEM
            FROM BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
            WHERE DT_INSTANTE BETWEEN DT_DATA_INICIO AND DT_DATA_FIM AND NU_CNPJ = '{cnpj}'
            GROUP BY NU_CNPJ, DT_DIA
        )
        
    SELECT
        c.NU_CNPJ AS NU_CNPJ,
        d.DT_DIA AS DT_DIA,
        NULLIF(QT_CONTAGEM, 0) AS QT_CONTAGEM
    FROM companies c
    CROSS JOIN date_range d
    LEFT JOIN counts t
        ON c.NU_CNPJ = t.NU_CNPJ AND d.DT_DIA = t.DT_DIA
    ORDER BY c.NU_CNPJ, d.DT_DIA
    """)

    VitDataDays["month"] = VitDataDays["DT_DIA"].dt.strftime("%Y-%m")

    return VitDataDays


def get_registered_vehicles(cnpj: str):
    Veiculos, _, _ = load_vit_data()
    vehicles = Veiculos[Veiculos["NU_CNPJ"] == cnpj].copy()
    vehicles = vehicles.drop(columns=["NU_CNPJ"])
    vehicles = vehicles.reset_index(drop=True)

    return vehicles


def get_vit_points(cnpj: str, date_range: tuple[date, date]):
    start_date = date_range[0].strftime("%Y-%m-%d")
    end_date = date_range[1].strftime("%Y-%m-%d")
    loaded_client = ch_client()
    points = loaded_client.query_df(
        f"""
        SELECT
            NO_PONTO,
            DS_TIPO_PONTO,
            CG_LATITUDE,
            CG_LONGITUDE,
            COUNT(*) AS QT_CONTAGEM
        FROM
            BD_ANALYTICS_SIR.MV_VIT_AVISTAMENTOS
        WHERE
            NU_CNPJ = '{cnpj}' AND
            DT_INSTANTE BETWEEN toDate('{start_date}') AND toDate('{end_date}')
        GROUP BY ALL
        ORDER BY QT_CONTAGEM DESC"""
    )
    return points


vit_params_desc = {
    "vel_med": "Os veículos deverão percorrer o trecho concedido com velocidade média de {x} km/h.",
    "soma_quatro_atrasos": "Em qualquer ponto da rodovia, a somatória dos atrasos com relação à frequência estabelecida para a inspeção de tráfego, a cada 4 viaturas, não poderá ser superior a {x} minutos.",
    "it": "Os serviços de Inspeção de tráfego deverão realizar ciclos com tempo médio de circulação de {x} minutos, em condições normais de operação.",
}


def get_vit_params(cnpj):
    loaded_client = ch_client()
    max_deploy = loaded_client.query_df(
        f"SELECT MAX(deploy_id) AS max_id FROM BD_PER.TB_PARAMETROS_VIT WHERE cnpj = '{cnpj}'"
    )["max_id"].values[0]
    params = loaded_client.query_df(
        f"SELECT * FROM BD_PER.TB_PARAMETROS_VIT WHERE cnpj = '{cnpj}' AND deploy_id = {max_deploy}"
    )

    md = ""
    if not params["vel_med"].isnull().all():
        md += f"- **Velocidade média (VMéd)**: {vit_params_desc['vel_med'].format(x=params['vel_med'].values[0])}\n"
    if not params["soma_quatro_atrasos"].isnull().all():
        md += f"- **Soma de quatro atrasos consecutivos (Σ4)**: {vit_params_desc['soma_quatro_atrasos'].format(x=params['soma_quatro_atrasos'].values[0])}\n"
    if not params["it"].isnull().all():
        md += f"- **Intervalo de tempo (IT)**: {vit_params_desc['it'].format(x=params['it'].values[0])}\n"

    st.markdown(md)

    return params


def get_company_eval(cnpj, date_range: tuple[date, date]):
    df_atrasos, df_eval = vit_data_function_tables(date_range)
    df_company = df_eval[df_eval["NU_CNPJ"] == cnpj].copy()

    checks = {"none": [], "all": [], "partial": []}

    months = defaultdict(list)

    for index, row in df_company.iterrows():
        if row["cumpriu"] == "Não":
            months[row["DT_MES"]].append({"tipo_param": row["tipo"], "cumpriu": "Não"})
            continue
        if row["cumpriu"] == "Sim":
            months[row["DT_MES"]].append({"tipo_param": row["tipo"], "cumpriu": "Sim"})
            continue
        if row["cumpriu"] == "-":
            months[row["DT_MES"]].append({"tipo_param": row["tipo"], "cumpriu": "-"})
            continue

    for month, val in months.items():
        # if all is Não, add to none
        # elif if all is Sim, add to all
        # else, add to partial
        month_checks = [m["cumpriu"] for m in val]
        if all(c == "Não" for c in month_checks):
            checks["none"].append(month)
            continue
        if all(c == "Sim" for c in month_checks):
            checks["all"].append(month)
            continue
        checks["partial"].append(month)

    # formatting months as MM/YYYY
    for key, value in checks.items():
        checks[key] = [f"{m[5:7]}/{m[0:4]}" for m in value]

    # pegando os dados de atrasos
    atrasos = df_atrasos[df_atrasos["NU_CNPJ"] == cnpj].copy()
    mean_atrasos = np.round(atrasos["atraso_mins"].mean(), 0).astype(int)
    std_atrasos = np.round(atrasos["atraso_mins"].std(), 0).astype(int)

    return df_company, checks, mean_atrasos, std_atrasos, atrasos
