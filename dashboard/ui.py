"""Small layout helpers shared by the pages."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PORTAL = "https://www.data.gov.qa/explore/dataset/"


def tidy(table: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """Round floats, show timestamps as dates and use text column names."""
    out = table.copy()
    for column in out.columns:
        if pd.api.types.is_float_dtype(out[column]):
            out[column] = out[column].round(decimals)
        elif pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.date
    out.columns = [str(c) for c in out.columns]
    return out


def chart(fig: go.Figure, table: pd.DataFrame, note: str | None = None) -> None:
    """A chart with its data one click away (the table view is the accessible twin)."""
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})
    if note:
        st.caption(note)
    with st.expander("Show the numbers"):
        st.dataframe(tidy(table), hide_index=True)


def findings(sentences: list[str]) -> None:
    if not sentences:
        st.info("Not enough data in the warehouse for written findings yet.")
        return
    with st.container(border=True):
        st.markdown("**What the data says**")
        st.markdown("\n".join(f"- {s}" for s in sentences))


def sources(*datasets: tuple[str, str]) -> None:
    """Caption with links to the portal pages of the datasets behind a page."""
    links = ", ".join(f"[{title}]({PORTAL}{dataset_id}/)" for title, dataset_id in datasets)
    st.caption(f"Source: Qatar Open Data Portal, {links}. Licence CC BY 4.0.")
