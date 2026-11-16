from typing import Optional

import h3
import pandas as pd
import plotly.express as px
import polars as pl
from shapely.geometry import Polygon, mapping

from constants import PURPLE_GREEN_RED_PALETTE


def h3_to_geojson(
    df: pd.DataFrame, h3_col: str = "h3", value_col: str = "value"
) -> dict:
    features = []
    for _, row in df.iterrows():
        h = row[h3_col]
        boundary = h3.cells_to_geo([h])["coordinates"][0]
        poly = Polygon(boundary)
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {"value": float(row[value_col]), "h3": h},
            }
        )

    return {"type": "FeatureCollection", "features": features}


def plot_h3_map(
    df: pl.DataFrame,
    h3_col: str = "h3",
    value_col: str = "value",
    range_color: tuple[float, float] = (0, 2),
    color_map: list[tuple[float, str]] | str = PURPLE_GREEN_RED_PALETTE,
    additional_hover_data: Optional[list[str]] = None,
    rename_value_col: Optional[str] = None,
    other_renames: Optional[dict[str, str]] = None,
):
    if additional_hover_data is None:
        additional_hover_data = []

    if rename_value_col is not None:
        df = df.with_columns(pl.col(value_col).alias(rename_value_col)).drop(value_col)
        value_col = rename_value_col
    if other_renames is not None:
        for old_name, new_name in other_renames.items():
            df = df.with_columns(pl.col(old_name).alias(new_name)).drop(old_name)
    pandas_df = df.to_pandas()
    geojson = h3_to_geojson(pandas_df, h3_col=h3_col, value_col=value_col)

    all_coords = []
    for f in geojson["features"]:
        coords = f["geometry"]["coordinates"][0]
        all_coords.extend(coords)
    if all_coords:
        lats = [c[1] for c in all_coords]
        lons = [c[0] for c in all_coords]
        center = {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons)}
    else:
        center = {"lat": 0, "lon": 0}

    # Create figure
    hover_data_dict = {
        h3_col: True,
        value_col: True,
    }
    for additional in additional_hover_data:
        hover_data_dict[additional] = True

    range_color_midpoint = (range_color[0] + range_color[1]) / 2
    fig = px.choropleth_map(
        pandas_df,
        geojson=geojson,
        locations=h3_col,
        color=value_col,
        featureidkey="properties.h3",
        center=center,
        zoom=8,
        opacity=0.7,
        hover_data=hover_data_dict,
        range_color=range_color,
        color_continuous_scale=color_map,
        color_continuous_midpoint=range_color_midpoint,
    )

    fig.update_layout(map_style="carto-positron")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    return fig


def plot_similarities_map(
    similarities: pl.DataFrame,
    h3_col: str = "h3",
    sim_col: str = "similarity",
    top_n: int | None = None,
):
    df = similarities.to_pandas()

    if top_n is not None:
        if sim_col in df.columns:
            df = df.nlargest(top_n, sim_col)
        else:
            df = df.head(top_n)

    geojson = h3_to_geojson(df, h3_col=h3_col, value_col=sim_col)

    # centro automático (mesma lógica que plot_h3_map)
    all_coords = []
    for f in geojson["features"]:
        coords = f["geometry"]["coordinates"][0]
        all_coords.extend(coords)
    if all_coords:
        lats = [c[1] for c in all_coords]
        lons = [c[0] for c in all_coords]
        center = {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons)}
    else:
        center = {"lat": 0, "lon": 0}

    fig = px.choropleth_map(
        df,
        geojson=geojson,
        locations=h3_col,
        color=sim_col,
        featureidkey="properties.h3",
        center=center,
        zoom=8,
        opacity=0.7,
        hover_data={h3_col: True, sim_col: True},
        color_continuous_scale="rdylgn_r",
    )

    fig.update_layout(map_style="carto-positron")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    return fig
