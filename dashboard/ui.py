"""Small layout helpers shared by the pages."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import i18n
from dashboard.i18n import tr

PORTAL = "https://www.data.gov.qa/explore/dataset/"

# Streamlit has no right-to-left setting, so Arabic mode flips the page with CSS.
# Charts, tables and sliders stay left to right on purpose: Plotly positions its
# text assuming that direction, the table grid is drawn on a canvas, and a slider
# drags the wrong way when flipped. charts.py and tidy() mirror them where it helps.
#
# Three things direction alone does not reach, found by checking in a browser:
# dropdown lists are attached to the page body outside .stApp; every element has
# text-align: left set on it; and a collapsed sidebar is slid to the left, which
# from the right-hand side would put it on top of the page, so it is hidden instead.
RTL_CSS = """
<style>
.stApp, [data-testid="stSelectboxVirtualDropdown"] { direction: rtl; }
[data-testid="stSidebar"] { transition: none; }
[data-testid="stSidebar"][data-collapsed="true"] { display: none; }
[data-testid="stElementContainer"] { text-align: start !important; }
[data-testid="stMarkdownContainer"] li {
    margin-left: 0;
    margin-right: 1.2rem;
    padding-left: 0;
    padding-right: 0.3rem;
}
[data-testid="stMetricValue"] { font-size: 1.6rem; }
[data-testid="stMetricDelta"] { font-size: 0.75rem; }
[data-testid="stPlotlyChart"],
[data-testid="stDataFrame"],
[data-testid="stSlider"],
code { direction: ltr; unicode-bidi: isolate; }
[data-testid="stSlider"] [data-testid="stWidgetLabel"] { direction: rtl; }
</style>
"""


def start_language() -> None:
    """Pick the language for this run: the switch if it was used, else ?lang=ar in the URL."""
    if "language" not in st.session_state:
        asked = st.query_params.get("lang")
        st.session_state["language"] = asked if asked in i18n.LANGUAGES else "en"
    i18n.set_language(st.session_state["language"])
    if i18n.is_arabic():
        st.query_params["lang"] = "ar"
    elif "lang" in st.query_params:
        del st.query_params["lang"]


def apply_direction() -> None:
    if i18n.is_arabic():
        st.html(RTL_CSS)


def language_switch() -> None:
    st.radio(
        "Language / اللغة",
        list(i18n.LANGUAGES),
        format_func=i18n.LANGUAGES.get,
        key="language",
        horizontal=True,
    )


def tidy(table: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """Round floats, show timestamps as dates and use text column names.

    In Arabic mode the headers are translated and the columns reversed, so the
    table reads from the right.
    """
    out = table.copy()
    for column in out.columns:
        if pd.api.types.is_float_dtype(out[column]):
            out[column] = out[column].round(decimals)
        elif pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.date
    out.columns = [str(c) for c in out.columns]
    if i18n.is_arabic():
        out = out.rename(columns=i18n.COLUMNS)
        out = out[out.columns[::-1]]
    return out


def chart(fig: go.Figure, table: pd.DataFrame, note: str | None = None) -> None:
    """A chart with its data one click away (the table view is the accessible twin)."""
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})
    if note:
        st.caption(note)
    with st.expander(tr("Show the numbers")):
        st.dataframe(tidy(table), hide_index=True)


def findings(sentences: list[str]) -> None:
    if not sentences:
        st.info(tr("Not enough data in the warehouse for written findings yet."))
        return
    with st.container(border=True):
        st.markdown(f"**{tr('What the data says')}**")
        st.markdown("\n".join(f"- {s}" for s in sentences))


def sources(*datasets: tuple[str, str]) -> None:
    """Caption with links to the portal pages of the datasets behind a page."""
    links = ", ".join(f"[{title}]({PORTAL}{dataset_id}/)" for title, dataset_id in datasets)
    st.caption(tr("Source: Qatar Open Data Portal, {links}. Licence CC BY 4.0.", links=links))
