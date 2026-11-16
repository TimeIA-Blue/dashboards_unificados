import polars as pl

PRE_SELECTED_COMPANY_CNPJ = "15090690000194"


DICT_CHAVE_VISUALIZACAO = {
    "Porcentagem de zeros": "PCT_ZERO",
    "Porcentagem de autoacionados": "PCT_AUTOACIONADO",
}

DICT_TIPO_VEICULO_RECURSO = {
    "Guincho Leve": "Mecânico",
    "Guincho Pesado": "Mecânico",
    "Ambulância C": "Médico",
    "Ambulância D": "Médico",
}

PURPLE_GREEN_RED_PALETTE = [
    (0.0, "rgb(128, 0, 128)"),  # Deep Purple
    (0.5, "rgb(0, 128, 0)"),  # Deep Green
    (1.0, "rgb(255, 0, 0)"),  # Bright Red
]


SIMILARITIES_COLUMNS = [
    "value",
    "std_value",
    "q_25",
    "q_50",
    "q_75",
    "min_value",
    "max_value",
    "QT_CONTAGEM",
]

SIMILARITY_EXPR = (
    pl.sum_horizontal(
        [(pl.col(f"{c}") - pl.col(f"{c}_compared")) ** 2 for c in SIMILARITIES_COLUMNS]
    )
    .sqrt()
    .alias("Distância")
)

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "zoomInMapbox",
        "zoomOutMapbox",
        "resetViewMapbox",
        "toggleSpikelines",
        "hoverClosestGeo",
        "hoverClosestGl2d",
    ],
    "modeBarButtonsToAdd": ["select", "lasso"],
}

RANDOM_SAMPLING_QUERY_PERCENTAGE = 5
SLOW_QUERY_THRESHOLD_SECONDS = 5.0
