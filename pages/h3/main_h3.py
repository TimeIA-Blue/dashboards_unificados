from base64 import b64encode

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from constants import (
    DICT_CHAVE_VISUALIZACAO,
    DICT_TIPO_VEICULO_RECURSO,
    PLOTLY_CONFIG,
    SIMILARITIES_COLUMNS,
    SIMILARITY_EXPR,
)
from plotting import plot_h3_map, plot_similarities_map
from queries import (
    get_data_with_res,
    get_raw_data_for_hexagons,
    get_stats_region,
    get_zeroing_data,
)

st.set_page_config(page_title="H3 Visual", layout="wide")


@st.cache_data
def get_available_concessionarias(data: pl.DataFrame) -> dict[str, str]:
    return {k: v for (k, v) in data[["NU_CNPJ", "NO_FANTASIA"]].iter_rows()}


@st.cache_data
def filter_by_concessionaria_recurso(
    data: pl.DataFrame, cnpj: str, tipo_recurso: str
) -> pl.DataFrame:
    return data.filter(
        [
            pl.col("NU_CNPJ") == cnpj,
            pl.col("DS_TIPO_SERVICO") == DICT_TIPO_VEICULO_RECURSO[tipo_recurso],
            pl.col("DS_TIPO_VEICULO_RECURSO") == tipo_recurso,
        ]
    )


def calculate_similarities(
    data: pl.DataFrame,
    first_h3: str,
) -> pl.DataFrame:
    normalized = data.select(
        [
            "CD_H3",
            *[
                ((pl.col(c) - pl.col(c).mean()) / pl.col(c).std()).alias(c)
                for c in SIMILARITIES_COLUMNS
            ],
        ]
    )
    cross_joined = (
        normalized.filter(pl.col("CD_H3") == first_h3)
        .join(
            normalized,
            how="cross",
            suffix="_compared",
        )
        .with_columns(SIMILARITY_EXPR)
    )
    return cross_joined.select(["CD_H3", "CD_H3_compared", "Distância"])


with open("public/cnso.png", "rb") as image_file:
    base64_str = b64encode(image_file.read())
    base64_encoded = base64_str.decode("utf-8")

_ = st.markdown(
    """
            <h1 style="text-align:center">Visualização estratégica com grid hexagonal</h1>
            """,
    unsafe_allow_html=True,
)

res = st.slider("Resolução H3", 0, 15, 6)
tabData, tabAnomalies = st.tabs(["Hexágonos", "Anomalias (% de zeros)"])

with tabData:
    data = get_data_with_res(res)
    available_concessionarias = get_available_concessionarias(data)
    concessionaria = st.selectbox(
        "Concessionária",
        available_concessionarias.keys(),
        format_func=lambda k: available_concessionarias[k],
    )
    tipo_recurso = st.selectbox("Tipo de Recurso", DICT_TIPO_VEICULO_RECURSO.keys())
    filtered_data = filter_by_concessionaria_recurso(data, concessionaria, tipo_recurso)

    filtered_data_with_coef = df = filtered_data.with_columns(
        [(pl.col("value") / pl.col("value").mean()).alias("Coef. comparativo")]
    )
    fig = plot_h3_map(
        filtered_data_with_coef,
        h3_col="CD_H3",
        value_col="Coef. comparativo",
        range_color=(0, 2),
    )
    sel_event = st.plotly_chart(
        fig,
        on_select="rerun",
        width="stretch",
        selection_mode=["points"],
        config=PLOTLY_CONFIG,
    )

    location = sel_event.get("selection", {}).get("points", [])

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    if location and location[0].get("location"):
        if location.__len__() == 1:
            selected_location = str(location[0].get("location"))
            st.write(f"Similaridade em relação ao hexágono: {selected_location}")
            similarities = calculate_similarities(filtered_data, selected_location)
            st.plotly_chart(
                plot_similarities_map(
                    similarities,
                    h3_col="CD_H3_compared",
                    sim_col="Distância",
                    top_n=None,
                ),
                width="stretch",
                config=PLOTLY_CONFIG,
            )

        stats_data = get_stats_region(
            concessionaria,
            tipo_recurso,
            res,
            hexagons=[loc["location"] for loc in location],
        )
        _cols = st.columns([1, 2, 1])
        with _cols[1]:
            upper_errors = [
                stats_data["maxInRegion"] - stats_data["avgInRegion"],
                stats_data["maxTotal"] - stats_data["avgTotal"],
            ]
            lower_errors = [
                stats_data["avgInRegion"] - stats_data["minInRegion"],
                stats_data["avgTotal"] - stats_data["minTotal"],
            ]
            fig = go.Figure(
                data=go.Bar(
                    x=["Região", "Total"],
                    y=[stats_data["avgInRegion"], stats_data["avgTotal"]],
                    error_y=dict(
                        type="data",
                        symmetric=False,
                        array=upper_errors,
                        arrayminus=lower_errors,
                        visible=True,
                    ),
                    marker_color=["#1f77b4", "#2ca02c"],
                )
            )
            fig.update_layout(
                title="Comparação: Região Selecionada x Global",
                yaxis={"title": "Valor médio e desvio padrão, em minutos"},
                # yaxis={"text": "Valor médio e desvio padrão"},
                autosize=False,
                width=1200,
                height=600,
            )
            st.plotly_chart(fig, False)
    else:
        st.info("Nenhum hexágono selecionado")

with tabAnomalies:
    zeroing_data = get_zeroing_data(res)
    available_concessionarias = get_available_concessionarias(zeroing_data)
    concessionaria = st.selectbox(
        "Concessionária",
        available_concessionarias.keys(),
        format_func=lambda k: available_concessionarias[k],
    )
    tipo_recurso = st.selectbox(
        "Tipo de Recurso", DICT_TIPO_VEICULO_RECURSO.keys(), key="selectboxAnomalies"
    )
    filtered_data = filter_by_concessionaria_recurso(
        zeroing_data, concessionaria, tipo_recurso
    )
    used_key = st.selectbox(
        "Chave de visualização",
        DICT_CHAVE_VISUALIZACAO.items(),
        format_func=lambda k: k[0],
        key="selectboxChaveVis",
    )
    match used_key[0]:
        case "Porcentagem de zeros":
            color_map = "rdylgn_r"
        case "Porcentagem de autoacionados":
            color_map = "viridis"
        case _:
            raise ValueError("Chave de visualização inválida")
    base_dict_rename = {
        v: k for k, v in DICT_CHAVE_VISUALIZACAO.items() if v != used_key[1]
    }
    base_dict_rename["COUNT_TOTAL"] = "Número de registros"
    hover_data = set(
        [*DICT_CHAVE_VISUALIZACAO.keys(), "Número de registros"]
    ).difference(used_key[1])
    fig = plot_h3_map(
        filtered_data,
        h3_col="h3",
        value_col=used_key[1],
        range_color=(0, 0.05),
        color_map=color_map,
        additional_hover_data=list(hover_data),
        rename_value_col=used_key[0],
        other_renames=base_dict_rename,
    )

    sel_event_anomalies = st.plotly_chart(
        fig,
        on_select="rerun",
        width="stretch",
        selection_mode=["points"],
        config=PLOTLY_CONFIG,
    )
    location = sel_event_anomalies.get("selection", {}).get("points", [])

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    if location and location[0].get("location"):
        hexagon_list = [loc["location"] for loc in location]
        raw_data = get_raw_data_for_hexagons(
            concessionaria, res, tipo_recurso, hexagon_list
        )

        if raw_data.__len__() == 0:
            st.markdown(
                "<h1 style='color:lightgreen'>Nenhum registro com intervalo de tempo zerado!</h1>",
                unsafe_allow_html=True,
            )
        else:
            region_availability = (
                filtered_data.filter(
                    [
                        pl.col("h3").is_in(hexagon_list),
                    ]
                )
                .select(
                    [
                        (
                            pl.col("COUNT_ZERO").sum() / pl.col("COUNT_TOTAL").sum()
                        ).alias("res")
                    ]
                )["res"]
                .item()
            )
            st.markdown(
                f"# Porcentagem de zeros na região: {region_availability * 100:.2f}%"
            )

            st.dataframe(raw_data)
            hist_chart = px.histogram(raw_data, x="Placa_Recurso")
            hist_chart.update_layout(
                xaxis_title_text="Placa do Recurso",
                yaxis_title_text="Quantidade de atendimentos zerados",
            )
            st.plotly_chart(hist_chart)
    else:
        st.info("Nenhum hexágono selecionado")
