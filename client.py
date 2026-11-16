from collections.abc import Sequence
from datetime import tzinfo
from json import dumps
from random import randint
from time import time
from typing import Any

import numpy as np
import streamlit as st
from clickhouse_connect.driver.exceptions import OperationalError
from clickhouse_connect.driver.external import ExternalData
from clickhouse_connect.driver.httpclient import HttpClient
from clickhouse_connect.driver.query import QueryContext, TzMode
from pandas import DataFrame

from constants import RANDOM_SAMPLING_QUERY_PERCENTAGE, SLOW_QUERY_THRESHOLD_SECONDS
from setup import get_general_logger, get_query_logger

TYPE_MAP = {
    "String": object,
    "FixedString": object,
    "DateTime": "datetime64[ns]",
    "DateTime64": "datetime64[ns]",
    "Date": "datetime64[ns]",
    "Float32": np.float32,
    "Float64": np.float64,
    "Int8": "Int8",
    "Int16": "Int16",
    "Int32": "Int32",
    "Int64": "Int64",
    "UInt8": "UInt8",
    "UInt16": "UInt16",
    "UInt32": "UInt32",
    "UInt64": "UInt64",
    "Bool": bool,
}


class LoggingClient(HttpClient):
    def _announce_query_start(self, query: str):
        general_logger = get_general_logger()
        general_logger.info(
            {
                "event": "query_start",
                "query": query,
            }
        )

    def _handle_client_log(self, start_time: float, end_time: float, query: str):
        duration = end_time - start_time
        if duration > SLOW_QUERY_THRESHOLD_SECONDS:
            general_logger = get_general_logger()
            query_logger = get_query_logger()
            general_logger.warning(
                {
                    "event": "slow_query",
                    "query": query,
                    "duration_seconds": duration,
                }
            )
        else:
            log = randint(0, 100)
            if log <= RANDOM_SAMPLING_QUERY_PERCENTAGE:
                query_logger = get_query_logger()
                query_logger.info(
                    dumps(
                        {
                            "start": start_time,
                            "end": end_time,
                            "query": query,
                            "duration_seconds": duration,
                        }
                    )
                )

    def query_df(
        self,
        query: str | None = None,
        parameters: Sequence | dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        query_formats: dict[str, str] | None = None,
        column_formats: dict[str, str] | None = None,
        encoding: str | None = None,
        use_none: bool | None = None,
        max_str_len: int | None = None,
        use_na_values: bool | None = None,
        query_tz: str | None = None,
        column_tzs: dict[str, str | tzinfo] | None = None,
        context: QueryContext | None = None,
        external_data: ExternalData | None = None,
        use_extended_dtypes: bool | None = None,
        transport_settings: dict[str, str] | None = None,
        tz_mode: TzMode | None = None,
    ) -> DataFrame:
        start_time = time()
        result = super().query_df(
            query,
            parameters,
            settings,
            query_formats,
            column_formats,
            encoding,
            use_none,
            max_str_len,
            use_na_values,
            query_tz,
            column_tzs,
            context,
            external_data,
            use_extended_dtypes,
            transport_settings,
            tz_mode,
        )
        end_time = time()
        self._handle_client_log(start_time, end_time, query or "")
        return result


def ch_client() -> LoggingClient:
    if st.session_state.get("ch_client") is not None:
        return st.session_state["ch_client"]

    client_config = {
        "host": st.secrets.clickhouse.host,
        "port": st.secrets.clickhouse.port,
        "username": st.secrets.clickhouse.username,
        "password": st.secrets.clickhouse.password,
        "database": st.secrets.clickhouse.database,
    }
    try:
        # TODO: Configure certificate reading
        client = LoggingClient(interface="https", **client_config)
    except OperationalError as e:
        get_general_logger().warning(
            {
                "event": "ch_client_https_initialization_failed",
                "error": str(e),
                "note": "This is expected if ClickHouse is not configured for HTTPS",
            }
        )

    try:
        client = LoggingClient(interface="http", **client_config)
    except OperationalError as e:
        get_general_logger().error(
            {
                "event": "ch_client_http_initialization_failed",
                "error": str(e),
            }
        )
        raise

    st.session_state["ch_client"] = client
    return client
