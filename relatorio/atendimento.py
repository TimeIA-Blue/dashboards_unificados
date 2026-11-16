from datetime import date

import pandas as pd
import polars as pl
import polars.selectors as pls
import streamlit as st
from pandas._libs import Timestamp
from pandas.core.frame import DataFrame

from client import ch_client
from queries import get_query_result
from queries.atendimento import AVAILABLE_ATENDIMENTO_QUERIES
from relatorio import GetGapsReturnDict, convert_and_plot_h3_map
from relatorio.reporter import SubReporter, SubReportSection

at_exp_formats = {
    1: "90% dos atendimentos devem ter intervalo de tempo entre acionamento e chegada menor ou igual a {value} minutos.",
    2: "A média dos 10% maiores intervalos de tempo entre acionamento e chegada deve ser menor ou igual a {value} minutos.",
    3: "A média dos 90% menores intervalos de tempo entre acionamento e chegada deve ser menor ou igual a {value} minutos.",
}


def at_get_gaps(
    cnpj: str, date_range: tuple[date, date]
) -> tuple[DataFrame, Timestamp, Timestamp, list[GetGapsReturnDict]]:
    t = get_query_result(
        AVAILABLE_ATENDIMENTO_QUERIES["get_gaps"],
        {
            "cnpj": cnpj,
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=False,
    )

    t["ST_ZERADO"] = t["QT_CONTAGEM"] == 0
    t["CD_GRUPO"] = (t["ST_ZERADO"] != t["ST_ZERADO"].shift()).cumsum()

    min_date: pd.Timestamp = t["DT_DIA"].min()
    max_date: pd.Timestamp = t["DT_DIA"].max()

    where_zero: DataFrame = t[t["ST_ZERADO"]]
    gaps = (
        where_zero.groupby("CD_GRUPO")
        .agg(start=("DT_DIA", "min"), end=("DT_DIA", "max"), length=("DT_DIA", "count"))
        .reset_index(drop=True)
    )

    gaps_as_dicts: list[GetGapsReturnDict] = gaps.to_dict(orient="records")  # ty: ignore[invalid-assignment]

    return t, min_date, max_date, gaps_as_dicts


def get_at_map_data(cnpj: str, date_range: tuple[date, date]) -> pl.DataFrame:
    ch_client().query("SET geotoh3_argument_order = 'lon_lat'").close()
    t = get_query_result(
        AVAILABLE_ATENDIMENTO_QUERIES["get_locations"],
        {
            "cnpj": cnpj,
            "resolution": "5",
            "date_start": date_range[0].strftime("%Y-%m-%d"),
            "date_end": date_range[1].strftime("%Y-%m-%d"),
        },
        use_polars=True,
    )
    return t


def average_above_q90(series: pl.Series):
    q90 = series.quantile(0.9, "higher")
    return series.filter(series > q90).mean()


def average_at_below_q90(series: pl.Series):
    q90 = series.quantile(0.9, "higher")
    return series.filter(series <= q90).mean()


class AtendimentoReporter(SubReporter):
    DATASET_NAME = "Atendimentos médicos e mecânicos"

    def list_params(self, df_pl: pl.DataFrame, company_name: str):
        general_params = df_pl.filter(pl.col("CD_RODOVIA").is_null())
        specific_params = df_pl.filter(pl.col("CD_RODOVIA").is_not_null())
        self.md("### Parâmetros operacionais estabelecidos")
        preamble_general = f"Para a concessionária {company_name}, foram estabelecidos pelo Programa de Exploração a Rodovia (PER) os seguintes parâmetros operacionais para os atendimentos médicos e mecânicos:"
        self.md(preamble_general)
        for (tipo_param,), data_params in general_params.group_by("CD_TIPO_PARAMETRO"):
            exp_param = at_exp_formats[tipo_param].format(value="X")
            self.md(f"- {exp_param}")
            pd_table = (
                data_params.select(
                    [
                        pl.col("CD_TIPO_RECURSO").alias("Tipo do Recurso"),
                        pl.col("VL_VALOR").cast(pl.Int64).alias("Valor (X)"),
                    ]
                )
                .to_pandas()
                .set_index("Tipo do Recurso", drop=True)
            )
            self.show_df(pd_table)
        for (rodovia,), data in specific_params.group_by("CD_RODOVIA"):
            preamble_rodovia = f"<span style='color:red'>Especificamente</span> para a rodovia com numeração **{rodovia}**:"
            self.md(preamble_rodovia)
            for (tipo_param,), data_params in data.group_by("CD_TIPO_PARAMETRO"):
                exp_param = at_exp_formats[tipo_param].format(value="X")
                self.md(f"- {exp_param}")
                pd_table = (
                    data_params.select(
                        [
                            pl.col("CD_TIPO_RECURSO").alias("Tipo do Recurso"),
                            pl.col("VL_VALOR").cast(pl.Int64).alias("Valor (X)"),
                        ]
                    )
                    .to_pandas()
                    .set_index("Tipo do Recurso", drop=True)
                )
                self.show_df(pd_table)

    def should_skip(self, cnpj: str, date_range: tuple[date, date]) -> str | None:
        total_count = get_query_result(
            AVAILABLE_ATENDIMENTO_QUERIES["get_total_count"],
            {
                "cnpj": cnpj,
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        ).row(0)[0]
        if total_count == 0:
            return "A concessionária não apresentou nenhum dado de atendimentos médicos e/ou mecânicos no período selecionado."

    def build_section(
        self, section: SubReportSection, cnpj: str, date_range: tuple[date, date]
    ):
        match section:
            case SubReportSection.VISAO_GERAL:
                self.build_visao_geral(cnpj, date_range)
            case SubReportSection.PARAMETROS_OPERACIONAIS:
                self.build_parametros_operacionais(cnpj, date_range)
            case SubReportSection.ANOMALIAS:
                self.build_anomalias(cnpj, date_range)
            case _:
                pass

    def build_visao_geral(self, cnpj: str, date_range: tuple[date, date]):
        _timeseries, min_date, max_date, gaps = at_get_gaps(cnpj, date_range)
        data_msg = "A concessionária apresentou dados completos para todos os dias do período analisado -- {periodo_inicio} a {periodo_fim}."
        if gaps:
            data_msg = "A concessionária apresentou dados **incompletos** para o período analisado ({periodo_inicio} a {periodo_fim}). Foram identificadas as seguintes lacunas."

        gaps_fmt: list[str] = []
        gaps_fmt_html: list[str] = []
        for gap in gaps:
            dias_fmt = "dias" if gap["length"] > 1 else "dia"
            gaps_fmt.append(
                f"* De {gap['start'].strftime('%d/%m/%Y')} a {gap['end'].strftime('%d/%m/%Y')} ({gap['length']} {dias_fmt})"
            )
            gaps_fmt_html.append(
                f"<li>De {gap['start'].strftime('%d/%m/%Y')} a {gap['end'].strftime('%d/%m/%Y')} ({gap['length']} {dias_fmt})</li>"
            )

        gaps_fmt_joined = "\n".join(gaps_fmt)
        data_fmt = data_msg.format(
            periodo_inicio=min_date.strftime("%d/%m/%Y"),
            periodo_fim=max_date.strftime("%d/%m/%Y"),
        )
        self.md(data_fmt)
        # plot time series of counts
        _ = st.line_chart(
            _timeseries.set_index("DT_DIA")["QT_CONTAGEM"],
            height=300,
            width="stretch",
        )
        self._current_report_html.append(
            "<div><img src='data:image/png;base64,{chart_data}'/></div>"
        )
        self.md(gaps_fmt_joined)

        self.md(gaps_fmt_joined)

        at_map_data = get_at_map_data(cnpj, date_range).with_columns(
            pl.col("QT_CONTAGEM").cast(pl.Float64)
        )
        fig = convert_and_plot_h3_map(
            at_map_data,
            h3_col="CD_H3",
            value_col="QT_CONTAGEM",
            rename_value_col="N. de atendimentos",
        )
        self.md("#### Localização dos atendimentos")

        _ = st.plotly_chart(fig, width="stretch")
        self.append_h3_map_snapshot(
            at_map_data["CD_H3"].to_pandas(),
            at_map_data["QT_CONTAGEM"].to_pandas(),
        )
        # vertical space to fit the copyright from osm
        self.md("<br><br>")
        coordinates_data = (
            at_map_data.with_columns(pl.col("QT_CONTAGEM").cast(int))
            .rename(
                {
                    "CD_H3": "Código H3",
                    "QT_CONTAGEM": "Total de atendimentos",
                }
            )
            .to_pandas()
            .to_csv(index=False)
            .encode("utf-8")
        )
        _ = st.download_button(
            "Baixar tabela de coordenadas",
            data=coordinates_data,
            file_name=f"atendimentos_coordenadas_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_coords_at_{cnpj}_{st.session_state.report_number}",
        )

    def build_parametros_operacionais(self, cnpj: str, date_range: tuple[date, date]):
        company_name = self.company_name(cnpj)
        first_calls_pl = get_query_result(
            AVAILABLE_ATENDIMENTO_QUERIES["get_first_calls"],
            {
                "cnpj": cnpj,
                "threshold_dist": "1000",
                "threshold_time": "0.5",
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        )
        params_pl = get_query_result(
            AVAILABLE_ATENDIMENTO_QUERIES["get_company_params"],
            {"cnpj": cnpj},
            use_polars=True,
        ).with_columns(
            pl.when(pl.col("DS_NOME_TRECHO").is_not_null())
            .then(pl.col("DS_NOME_TRECHO"))
            .otherwise(pl.col("CD_RODOVIA").cast(pl.String))
            .alias("key_trecho")
        )
        self.list_params(params_pl, company_name)
        on_pivot = ["CD_TIPO_PARAMETRO", "VL_VALOR"]
        index_cols = list(set(params_pl.columns) - set(on_pivot))
        params_pl = params_pl.pivot("CD_TIPO_PARAMETRO", index=index_cols).rename(
            {"1": "param_q_90", "2": "param_med_10", "3": "param_med_90"}, strict=False
        )
        has_params = {
            c[6:].lower() for c in params_pl.columns if c.startswith("param_")
        }
        first_columns = ["CD_RODOVIA", "DS_TIPO_RODOVIA", "DS_NOME_TRECHO"]

        group_keys = [
            "key_trecho",
            "DT_MES",
            "DS_TIPO_SERVICO",
            "DS_TIPO_VEICULO_RECURSO",
        ]
        stats_df = first_calls_pl.group_by(group_keys).agg(
            [
                pl.col(first_columns).first(),
                pl.col("CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS")
                .quantile(0.9, "higher")
                .alias("Q_90"),
                pl.col("CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS")
                .map_batches(average_above_q90, pl.Float64, returns_scalar=True)
                .alias("MED_10"),
                pl.col("CALC_DELTA_ACIONAMENTO_CHEGADA_MINUTOS")
                .map_batches(average_at_below_q90, pl.Float64, returns_scalar=True)
                .alias("MED_90"),
                pl.col("Z").sum().alias("QNT_Z"),
                pl.col("Z_JUSTIFICADO").sum().alias("QNT_Z_JUST"),
                pl.len().alias("CNT"),
            ]
        )
        full_stats = stats_df.with_columns(
            [
                (
                    pl.concat_str(
                        [
                            pl.when(pl.col("DS_TIPO_RODOVIA") == "Federal")
                            .then(pl.lit("BR-"))
                            .otherwise(pl.lit("ESTADUAL-")),
                            pl.col("CD_RODOVIA").cast(pl.String).str.zfill(3),
                        ]
                    )
                ).alias("RODOVIA_FORMATTED"),
            ]
        )
        full_stats = full_stats.with_columns(
            pl.when(pl.col("DS_NOME_TRECHO").is_not_null())
            .then(pl.col("DS_NOME_TRECHO"))
            .otherwise(pl.col("RODOVIA_FORMATTED"))
            .alias("DISPLAY_NAME")
        )
        keys_left = group_keys.copy()
        keys_left.remove("DT_MES")
        keys_right = ["key_trecho", "DS_TIPO_SERVICO", "CD_TIPO_RECURSO"]
        params_with_key = params_pl.filter(pl.col("key_trecho").is_not_null())
        params_without_key = params_pl.filter(pl.col("key_trecho").is_null())

        join1 = full_stats.join(
            params_with_key, left_on=keys_left, right_on=keys_right, how="left"
        )

        keys_left_no_key = [k for k in keys_left if k != "key_trecho"]
        keys_right_no_key = [k for k in keys_right if k != "key_trecho"]

        join2 = full_stats.join(
            params_without_key,
            left_on=keys_left_no_key,
            right_on=keys_right_no_key,
            how="left",
        )

        exprs: list[pl.Expr] = []

        for param in has_params:
            exprs.append(
                pl.when(pl.col(f"param_{param}").is_null())
                .then(join2[f"param_{param}"])
                .otherwise(pl.col(f"param_{param}"))
                .alias(f"param_{param}")
            )
        full_stats = join1.with_columns(exprs).select(~pls.ends_with("_right"))

        def generate_expr(param_id: str):
            param_lower = param_id.lower()
            value_col = pl.col(param_id.upper()).replace(None, 0.0)
            param_col = pl.col(f"param_{param_lower}")
            param_doesnt_exist = param_col.is_null()
            value_bigger = value_col > param_col
            return (
                pl.when(param_doesnt_exist)
                .then(pl.lit(0))
                .otherwise(pl.when(value_bigger).then(pl.lit(-1)).otherwise(pl.lit(1)))
                .alias(f"{param_lower}_check")
            )

        display_group_keys = [
            "DT_MES",
            "DISPLAY_NAME",
            "DS_TIPO_SERVICO",
            "DS_TIPO_VEICULO_RECURSO",
        ]
        full_stats = full_stats.select(
            pls.exclude(
                [pls.starts_with("deploy"), pls.starts_with("km_"), pl.col("rodovia")]
            )
        ).with_columns(
            *[generate_expr(p) for p in has_params],
        )

        dataframes: dict[str, pl.DataFrame] = {}
        params_renamed = {
            "q_90": "Tempo de chegada (90% abaixo de) (minutos)",
            "med_10": "Tempo de chegada (média dos 10% maiores) (minutos)",
            "med_90": "Tempo de chegada (média dos 90% menores) (minutos)",
        }
        params_renamed_reverse = {v: k for k, v in params_renamed.items()}
        for param in has_params:
            expr = (
                pl.col(f"{param}_check")
                .replace_strict(
                    {
                        -1: "Não cumprido",
                        0: "Não verificado",
                        1: "Cumprido",
                    }
                )
                .first()
            )
            dataframes[params_renamed[param]] = (
                full_stats.group_by(display_group_keys)
                .agg(expr)
                .with_columns(pl.col("DT_MES").dt.strftime("%Y/%m"))
                .rename(
                    {
                        f"{param}_check": "Indicador de cumprimento",
                        "DT_MES": "Ano/Mês",
                        "DISPLAY_NAME": "Trecho ou Rodovia",
                        "DS_TIPO_SERVICO": "Tipo de Serviço",
                        "DS_TIPO_VEICULO_RECURSO": "Tipo de Recurso",
                    }
                )
            )
        self.md("### Indicadores de cumprimento dos parâmetros operacionais")

        fmt_text = """No quadro abaixo são apresentados os indicadores de cumprimento dos parâmetros operacionais
        estabelecidos para os atendimentos médicos e mecânicos realizados pela concessionária. Para facilitar a visualização, os indicadores foram
        agrupados, não sendo possível verificar cada mês individualmente. Isso permite uma maior clareza na análise da tendência geral. Para avaliar
        cada mês de forma manual, recomenda-se que se exporte os dados brutos e realize uma análise sobre os mesmos."""
        self.md(fmt_text)
        for param_inner, df in dataframes.items():
            print(param_inner)
            self.md(f"#### Parâmetro: {param_inner}")
            pd_table = df.to_pandas().set_index(
                [
                    "Ano/Mês",
                    "Trecho ou Rodovia",
                    "Tipo de Serviço",
                    "Tipo de Recurso",
                ],
                drop=True,
            )
            self.show_df(pd_table)
            _ = st.download_button(
                "Baixar sumarização do parâmetro",
                data=df.to_pandas().to_csv(index=False).encode("utf-8-sig"),
                file_name=(
                    f"atendimentos_parametro_"
                    f"{params_renamed_reverse[param_inner]}_{cnpj}.csv"
                ),
                mime="text/csv",
                icon=":material/download:",
                key=f"download_at_{params_renamed_reverse[param_inner]}_{cnpj}_{st.session_state.report_number}",
            )
        full_params = (
            pl.concat(list(dataframes.values())).to_pandas()
            if dataframes
            else pd.DataFrame()
        )
        _ = st.download_button(
            "Baixar tabela completa",
            data=full_params.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"atendimentos_parametros_{cnpj}.csv",
            mime="text/csv",
            icon=":material/download:",
            key=f"download_at_fullparams_{cnpj}_{st.session_state.report_number}",
        )

    def build_anomalias(self, cnpj: str, date_range: tuple[date, date]):
        zeroed_data_monthly_pl = get_query_result(
            AVAILABLE_ATENDIMENTO_QUERIES["get_zeroed_registers"],
            {
                "cnpj": cnpj,
                "threshold_dist": "1000",
                "threshold_time": "0.5",
                "date_start": date_range[0].strftime("%Y-%m-%d"),
                "date_end": date_range[1].strftime("%Y-%m-%d"),
            },
            use_polars=True,
        )
        zeroed_data_monthly_pl = zeroed_data_monthly_pl.with_columns(
            pl.col("DT_MES").dt.cast_time_unit("ms")
        )
        min_date = date_range[0]
        max_date = date_range[1]
        range_expr = pl.datetime_range(
            min_date, max_date, interval="1mo", time_unit="ms"
        )
        time_range_pl = pl.select(range_expr.alias("date"))
        with_null_data_pl = time_range_pl.join(
            zeroed_data_monthly_pl,
            left_on="date",
            right_on="DT_MES",
            how="left",
        ).fill_null(0)
        min_date_str = min_date.strftime("%m/%Y")
        max_date_str = max_date.strftime("%m/%Y")
        with_null_data_pl = with_null_data_pl.with_columns(
            [
                (pl.col("QT_ZEROS") * 100 / pl.col("QT_CONTAGEM"))
                .round(2)
                .alias("pct_z"),
                (
                    pl.when(pl.col("QT_ZEROS") > 0)
                    .then(
                        (pl.col("QT_AUTOACIONADOS") * 100 / (pl.col("QT_ZEROS"))).round(
                            2
                        )
                    )
                    .otherwise(pl.lit(None))
                ).alias("pct_autoacionado"),
                (
                    pl.when(pl.col("QT_ZEROS") > 0)
                    .then(
                        (pl.col("QT_INVALIDOS") * 100 / (pl.col("QT_ZEROS"))).round(2)
                    )
                    .otherwise(pl.lit(None))
                ).alias("pct_invalido"),
            ]
        )
        min_zeroed_pct: float = with_null_data_pl.select("pct_z").min().item()
        mean_zeroed_pct: float = with_null_data_pl.select("pct_z").mean().item()
        max_zeroed_pct: float = with_null_data_pl.select("pct_z").max().item()
        mean_selfreport_pct: float = (
            with_null_data_pl.select("pct_autoacionado").mean().item()
        )
        fmt_text = f"No período de {min_date_str} - {max_date_str}, a média mensal de registros zerados foi de {mean_zeroed_pct:.2f}% do total de casos."
        fmt_text += f"\n\nO valor mínimo da série histórica é de {min_zeroed_pct:.2f}%, enquanto o máximo atinge {max_zeroed_pct:.2f}%."
        fmt_text += f"\n\nQuando analisamos os registros zerados, verificamos que {mean_selfreport_pct:.2f}% deles foram potencialmente autoacionados pelos próprios recursos que realizaram o atendimento."
        if mean_zeroed_pct > 0.05 and mean_selfreport_pct < 0.5:
            fmt_text += "\n\nComo a taxa de registros zerados é superior a 5%, dos quais a metade não são autoacionados, logo, conclui-se que há um padrão de preenchimento indesejado por parte da concessionária."
        elif mean_zeroed_pct > 0.05 and mean_selfreport_pct >= 0.5:
            fmt_text += "\n\nA concessionária apresenta um padrão aceitável de preenchimento dos registros de atendimento, dado que a maioria dos registros zerados são considerados autoacionados, não configurando tentativa de mascaramento dos dados."
        else:
            fmt_text += "\n\nA concessionária apresenta um padrão aceitável de preenchimento dos registros de atendimento, dado que a taxa de registros zerados é inferior a 5% do total de atendimentos registrados."
        fmt_text += "\n\nA tabela abaixo apresenta a série histórica mensal dos registros com intervalo de tempo zerado."
        display_data_pd = (
            with_null_data_pl.rename(
                {
                    "date": "Mês",
                    "QT_ZEROS": "Zerados",
                    "QT_AUTOACIONADOS": "Autoacionados",
                    "QT_INVALIDOS": "Inválidos",
                    "QT_CONTAGEM": "Total",
                    "pct_z": "% zerados",
                    "pct_autoacionado": "% autoacionados",
                    "pct_invalido": "% inválidos",
                }
            )
            .with_columns(pl.col("Mês").dt.strftime("%Y/%m"))
            .to_pandas()
            .set_index("Mês", drop=True)
        )
        self.md("### Anomalias - Registros com intervalo de tempo zerado")
        self.md(fmt_text)
        self.show_df(display_data_pd)
        # get html string instead of saving to file
        pd_html = display_data_pd.to_html()
        self._current_report_html.append(f"<div>{pd_html}</div>")
        _ = st.download_button(
            "Baixar tabela de informações de registros zerados",
            data=display_data_pd.to_csv().encode("utf-8"),
            file_name=f"atendimentos_registros_zerados_{cnpj}.csv",
            mime="text/csv",
            key=f"download_at_zeroed_csv_{cnpj}_{st.session_state.report_number}",
        )
