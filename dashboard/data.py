"""Read the marts from DuckDB.

Each query opens a short-lived read-only connection and the result is cached
for ten minutes. Holding a connection open for the whole session would lock
the file and stop `python -m pipeline run` from refreshing it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from dashboard.i18n import tr
from pipeline.config import Settings


def warehouse_path() -> Path:
    return Settings.from_env().warehouse_path


@st.cache_data(ttl=600, show_spinner=False)
def _query(sql: str, path: str) -> pd.DataFrame:
    con = duckdb.connect(path, read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def query(sql: str) -> pd.DataFrame:
    return _query(sql, str(warehouse_path()))


def require_warehouse() -> None:
    """Stop the page with a helpful message when the pipeline has not run yet."""
    path = warehouse_path()
    if not path.exists():
        st.error(
            tr(
                "No warehouse found at `{path}`. Build it first with `python -m pipeline run`.",
                path=path,
            )
        )
        st.stop()


def annual() -> pd.DataFrame:
    return query("select * from marts.mart_annual_indicators order by year")


def labour() -> pd.DataFrame:
    return query("select * from marts.fct_labour_market_quarterly order by quarter_start, sex")


def cpi() -> pd.DataFrame:
    return query("select * from marts.fct_cpi_monthly order by month_start, group_code")


def inflation() -> pd.DataFrame:
    return query("select * from marts.fct_inflation_annual order by year, group_code")


def travel() -> pd.DataFrame:
    return query("select * from marts.fct_travel_monthly order by month_start")


def utilities_national() -> pd.DataFrame:
    return query("select * from marts.fct_utilities_national_annual order by year")


def utilities_zones() -> pd.DataFrame:
    return query("select * from marts.fct_utilities_zone_annual order by year, zone_number")


def manifest() -> pd.DataFrame:
    return query("select * from audit.source_manifest order by source_key")


def latest_checks() -> pd.DataFrame:
    return query(
        """
        select * from audit.check_results
        where run_id = (select arg_max(run_id, checked_at) from audit.check_results)
        order by case status when 'fail' then 0 when 'warn' then 1 else 2 end, check_name
        """
    )


def latest_model_runs() -> pd.DataFrame:
    return query(
        """
        select * from audit.model_runs
        where run_id = (select arg_max(run_id, finished_at) from audit.model_runs)
        order by case layer when 'staging' then 0 when 'intermediate' then 1 else 2 end, model
        """
    )


def has_table(schema: str, name: str) -> bool:
    found = query(
        "select count(*) as n from information_schema.tables "
        f"where table_schema = '{schema}' and table_name = '{name}'"
    )
    return bool(found["n"].iloc[0])
