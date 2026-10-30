"""Dashboard entry point.

    streamlit run dashboard/app.py

Reads the marts built by `python -m pipeline run`. The warehouse location
follows the same settings as the pipeline (QODP_DATA_DIR / QODP_WAREHOUSE).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from dashboard import data

st.set_page_config(page_title="Qatar Open Data", layout="wide")

PAGES = [
    st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("views/population.py", title="Population and jobs", icon=":material/groups:"),
    st.Page("views/prices.py", title="Prices", icon=":material/sell:"),
]

navigation = st.navigation(PAGES)
with st.sidebar:
    st.caption(
        "Data from the [Qatar Open Data Portal](https://www.data.gov.qa) (CC BY 4.0), "
        "refreshed with `python -m pipeline run`."
    )
data.require_warehouse()
navigation.run()
