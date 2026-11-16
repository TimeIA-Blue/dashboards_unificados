from typing import Any, TypedDict

import h3
import polars as pl
from pandas._libs import Timestamp
from pandas.core.api import DataFrame as PandasDataFrame
from plotly.express import choropleth_map
from polars import DataFrame as PolarsDataFrame
from shapely.geometry import Polygon, mapping

from .reporter import Reporter, SubReporter, SubReportSection


class GetGapsReturnDict(TypedDict):
    group: int
    start: Timestamp
    end: Timestamp
    length: int


class GeoJSONDict(TypedDict):
    type: str
    geometry: dict[str, Any]
    properties: dict[str, Any]


class GeoJSONFeatureCollectionDict(TypedDict):
    type: str
    features: list[GeoJSONDict]


def h3_to_geojson(
    df: PandasDataFrame, h3_col: str = "h3", value_col: str = "value"
) -> GeoJSONFeatureCollectionDict:
    features: list[GeoJSONDict] = []
    for _, row in df.iterrows():
        h: str = row[h3_col]  # pyright: ignore[reportAny]
        v = row[value_col]
        boundary = h3.cells_to_geo([h])["coordinates"][0]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        poly = Polygon(boundary)  # pyright: ignore[reportArgumentType]
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {"value": float(v), "h3": h},
            }
        )

    return {"type": "FeatureCollection", "features": features}


def convert_and_plot_h3_map(
    df: PolarsDataFrame,
    h3_col: str = "h3",
    value_col: str = "value",
    range_color: tuple[float, float] | None = None,
    color_map: list[tuple[float, str]] | str = "Viridis",
    additional_hover_data: list[str] | None = None,
    rename_value_col: str | None = None,
    other_renames: dict[str, str] | None = None,
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

    range_color_midpoint: float | None = None
    if range_color is not None:
        range_color_midpoint = (range_color[0] + range_color[1]) / 2
    fig = choropleth_map(
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


__all__ = [
    "Reporter",
    "SubReporter",
    "SubReportSection",
]
