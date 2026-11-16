from logging import Formatter, Logger, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from sys import stdout

import streamlit as st

GENERAL_LOG_PATH = Path("logs/app.log")
GENERAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
JSON_QUERIES_PATH = Path("logs/queries.log")
JSON_QUERIES_PATH.parent.mkdir(parents=True, exist_ok=True)


@st.cache_resource
def get_general_logger():
    log = Logger("streamlit_app_logger")
    stdout_handler = StreamHandler(stdout)

    if not GENERAL_LOG_PATH.is_file():
        GENERAL_LOG_PATH.touch()
    file_handler = RotatingFileHandler(
        GENERAL_LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=7
    )
    formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stdout_handler.setFormatter(formatter)
    log.addHandler(stdout_handler)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    log.setLevel("DEBUG")
    return log


@st.cache_resource
def get_query_logger():
    log = Logger("query_logger")
    if not JSON_QUERIES_PATH.is_file():
        JSON_QUERIES_PATH.touch()
    file_handler = RotatingFileHandler(
        JSON_QUERIES_PATH, maxBytes=5 * 1024 * 1024, backupCount=7
    )
    formatter = Formatter("%(asctime)s %(message)s")
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    log.setLevel("DEBUG")
    return log
