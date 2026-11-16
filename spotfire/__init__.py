import streamlit as st

from client import ch_client


def format_seconds(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}min")
    if s > 0 or not parts:
        parts.append(f"{s}s")
    return "".join(parts)


@st.cache_data(ttl=21600)
def get_company_names():
    client = ch_client()
    company_names = (
        client.query_df("SELECT * FROM BD_PER.TB_PARAMETROS_CONCESSIONARIAS")
        .set_index("NU_CNPJ")
        .to_dict(orient="index")
    )
    company_names = {
        k: v["NO_FANTASIA"] for k, v in company_names.items() if k is not None
    }
    return company_names
