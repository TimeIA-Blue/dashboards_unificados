from abc import ABC, abstractmethod
from base64 import b64encode
from collections.abc import Mapping
from datetime import date
from enum import Enum
from io import BytesIO
from textwrap import dedent
from typing import Final

import contextily as ctx
import h3
import markdown
import matplotlib
import pandas as pd
import streamlit as st

matplotlib.use("Agg")
import matplotlib.pyplot as plt


class SubReportSection(Enum):
    VISAO_GERAL = 0
    PARAMETROS_OPERACIONAIS = 1
    ANOMALIAS = 2


SECTION_LABELS: Final[Mapping[SubReportSection, str]] = {
    SubReportSection.VISAO_GERAL: "Visão Geral",
    SubReportSection.PARAMETROS_OPERACIONAIS: "Parâmetros Operacionais",
    SubReportSection.ANOMALIAS: "Anomalias",
}


class SubReporter(ABC):
    DATASET_NAME = "__unset__"

    def __init__(
        self,
        selected_companies_cnpj: list[str],
        print_company_name: bool,
        selected_sections: list[SubReportSection],
        companies_data: pd.DataFrame,
    ):
        self.companies_data = companies_data
        self.selected_companies_cnpj = selected_companies_cnpj.copy()
        self.print_company_name = print_company_name
        self.selected_sections = selected_sections.copy()
        self._current_report_html: list[str] = []

    @abstractmethod
    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        pass

    @abstractmethod
    def build_section(
        self, section: SubReportSection, cnpj: str, date_range: tuple[date, date]
    ):
        pass

    def md(self, md: str):
        normalized_md = dedent(md).strip()
        _ = st.markdown(normalized_md, unsafe_allow_html=True)
        self._current_report_html.append(normalized_md)

    def show_df(self, df: pd.DataFrame):
        _ = st.dataframe(df)
        self._current_report_html.append(df.to_html())

    def show_table(self, df: pd.DataFrame):
        _ = st.table(df)
        self._current_report_html.append(df.to_html())

    def append_line_chart_snapshot(self, values: pd.Series):
        figure, axis = plt.subplots(figsize=(10, 4), dpi=150)
        axis.plot(values.index, values.values, color="#2f80ed")
        axis.grid(alpha=0.2)
        figure.autofmt_xdate()
        figure.tight_layout()
        self._append_figure_snapshot(figure)

    def append_point_map_snapshot(
        self,
        latitude: pd.Series,
        longitude: pd.Series,
        size: pd.Series | None = None,
        color: pd.Series | None = None,
    ):
        map_data = pd.DataFrame({"latitude": latitude, "longitude": longitude})
        if size is not None:
            map_data["size"] = pd.to_numeric(size, errors="coerce")
        map_data = map_data.dropna(subset=["latitude", "longitude"])

        figure, axis = plt.subplots(figsize=(10, 5), dpi=300)
        if "size" in map_data:
            max_size = map_data["size"].clip(lower=0).max()
            point_size = (
                20 + 180 * (map_data["size"].clip(lower=0) / max_size) ** 0.5
                if max_size > 0
                else 30
            )
        else:
            point_size = 30

        point_color: str | list[str] = "#2f80ed"
        if color is not None:
            color_values = color.loc[map_data.index]
            if pd.api.types.is_bool_dtype(color_values):
                point_color = [
                    "#d62728" if is_anomalous else "#ffd700"
                    for is_anomalous in color_values
                ]
            else:
                point_color = color_values.tolist()

        axis.scatter(
            map_data["longitude"],
            map_data["latitude"],
            s=point_size,
            c=point_color,
            alpha=0.7,
            edgecolors="white",
            linewidths=0.4,
        )
        axis.set_facecolor("#f3f4f6")
        x_min, x_max = map_data["longitude"].min(), map_data["longitude"].max()
        y_min, y_max = map_data["latitude"].min(), map_data["latitude"].max()
        x_padding = max((x_max - x_min) * 0.08, 0.01)
        y_padding = max((y_max - y_min) * 0.08, 0.01)
        axis.set_xlim(x_min - x_padding, x_max + x_padding)
        axis.set_ylim(y_min - y_padding, y_max + y_padding)
        try:
            ctx.add_basemap(
                axis,
                source=ctx.providers.Esri.WorldStreetMap,  # ty: ignore[missing-attribute]
                crs="EPSG:4326",
                zoom_adjust=-1,
                reset_extent=False,
            )
        except (OSError, ValueError):
            axis.grid(color="#d1d5db", alpha=0.6)
        axis.set_aspect("auto")
        axis.set_axis_off()
        figure.tight_layout()
        self._append_figure_snapshot(figure)

    def append_h3_map_snapshot(self, cells: pd.Series, values: pd.Series):
        figure, axis = plt.subplots(figsize=(10, 5), dpi=150)
        value_min = values.min()
        value_max = values.max()
        value_range = value_max - value_min
        for cell, value in zip(cells, values):
            boundary = h3.cell_to_boundary(cell)
            polygon = [(longitude, latitude) for latitude, longitude in boundary]
            normalized = (value - value_min) / value_range if value_range else 0.5
            axis.fill(
                *zip(*polygon),
                color=plt.get_cmap("viridis")(normalized),
                alpha=0.7,
                edgecolor="white",
                linewidth=0.3,
            )
        axis.set_xlabel("Longitude")
        axis.set_ylabel("Latitude")
        axis.grid(alpha=0.2)
        figure.tight_layout()
        self._append_figure_snapshot(figure)

    def _append_figure_snapshot(self, figure):
        image = BytesIO()
        figure.savefig(image, format="png", bbox_inches="tight")
        plt.close(figure)
        encoded_image = b64encode(image.getvalue()).decode("ascii")
        self._current_report_html.append(
            f"<div><img src='data:image/png;base64,{encoded_image}'/></div>"
        )

    def company_name(self, cnpj: str) -> str:
        return self.companies_data.loc[
            self.companies_data["NU_CNPJ"] == cnpj, "NO_FANTASIA"
        ].values[0]

    def build_report(self, date_range: tuple[date, date]) -> str:
        for cnpj in self.selected_companies_cnpj:
            company_name = self.company_name(cnpj)
            if self.print_company_name:
                self.md(f"## {company_name}")
            for section in self.selected_sections:
                self.build_section(section, cnpj, date_range)
        return markdown.markdown("\n".join(self._current_report_html))


class Reporter:
    def __init__(
        self,
        subreporters_cls: list[type[SubReporter]],
        selected_companies_cnpj: list[str],
        selected_sections: list[SubReportSection],
        company_first: bool,
        companies_data: pd.DataFrame,
    ):
        self.companies_data = companies_data
        self.subreporters_cls = subreporters_cls.copy()
        self.selected_sections = selected_sections.copy()
        self.selected_companies_cnpj = selected_companies_cnpj.copy()
        self.company_first = company_first
        self._current_report_html = []

    def company_name(self, cnpj: str) -> str:
        return self.companies_data.loc[
            self.companies_data["cnpj"] == cnpj, "fantasia"
        ].values[0]

    def build_report(self, date_range: tuple[date, date]) -> str:
        if self.company_first:
            for cnpj in self.selected_companies_cnpj:
                company_name = self.company_name(cnpj)
                _ = st.markdown(f"# {company_name}")
                self._current_report_html.append(f"<h1>{company_name}</h1>")
                for subreporter_cls in self.subreporters_cls:
                    subreporter = subreporter_cls(
                        selected_companies_cnpj=[cnpj],
                        print_company_name=False,
                        selected_sections=self.selected_sections,
                        companies_data=self.companies_data,
                    )
                    should_skip_msg = subreporter.should_skip(cnpj, date_range)
                    if should_skip_msg is not None:
                        _ = st.markdown(f"**{should_skip_msg}**")
                        self._current_report_html.append(
                            f"<p><strong>{should_skip_msg}</strong></p>"
                        )
                        continue
                    _ = st.markdown(f"## {subreporter_cls.DATASET_NAME}")
                    self._current_report_html.append(
                        f"<h2>{subreporter_cls.DATASET_NAME}</h2>"
                    )
                    subreport_html = subreporter.build_report(date_range)
                    self._current_report_html.append(subreport_html)
        else:
            for subreporter_cls in self.subreporters_cls:
                subreporter = subreporter_cls(
                    selected_companies_cnpj=self.selected_companies_cnpj,
                    print_company_name=True,
                    selected_sections=self.selected_sections,
                    companies_data=self.companies_data,
                )
                should_skip_all = True
                for cnpj in self.selected_companies_cnpj:
                    should_skip_msg = subreporter.should_skip(cnpj, date_range)
                    if should_skip_msg is None:
                        should_skip_all = False
                        break
                if should_skip_all:
                    _ = st.markdown(
                        f"**Nenhum dado disponível para o conjunto de empresas selecionadas no dataset {subreporter_cls.DATASET_NAME}.**"
                    )
                    self._current_report_html.append(
                        f"<p><strong>Nenhum dado disponível para o conjunto de empresas selecionadas no dataset {subreporter_cls.DATASET_NAME}.</strong></p>"
                    )
                    continue
                _ = st.markdown(f"# {subreporter_cls.DATASET_NAME}")
                self._current_report_html.append(
                    f"<h1>{subreporter_cls.DATASET_NAME}</h1>"
                )
                subreport_html = subreporter.build_report(date_range)
                self._current_report_html.append(subreport_html)
        return "\n".join(self._current_report_html)
