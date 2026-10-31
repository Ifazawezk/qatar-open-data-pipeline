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

from dashboard import data, ui
from dashboard.i18n import tr

ui.start_language()
st.set_page_config(page_title=tr("Qatar Open Data"), layout="wide")
ui.apply_direction()

PAGES = [
    st.Page("views/overview.py", title=tr("Overview"), icon=":material/dashboard:", default=True),
    st.Page("views/population.py", title=tr("Population and jobs"), icon=":material/groups:"),
    st.Page("views/prices.py", title=tr("Prices"), icon=":material/sell:"),
    st.Page("views/travel.py", title=tr("Travel and hotels"), icon=":material/flight:"),
    st.Page("views/utilities.py", title=tr("Electricity and water"), icon=":material/bolt:"),
    st.Page(
        "views/pipeline_health.py",
        title=tr("Pipeline health"),
        icon=":material/fact_check:",
        url_path="pipeline",
    ),
]

navigation = st.navigation(PAGES)
with st.sidebar:
    ui.language_switch()
    st.caption(
        tr(
            "Data from the [Qatar Open Data Portal](https://www.data.gov.qa) (CC BY 4.0), "
            "refreshed with `python -m pipeline run`."
        )
    )
data.require_warehouse()
navigation.run()
