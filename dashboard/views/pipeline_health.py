import pandas as pd
import streamlit as st

from dashboard import data

st.title("Pipeline health")
st.caption(
    "Where the data came from, when it was fetched, and how the latest data tests went. "
    "The full data catalog with lineage is in docs/data_catalog.md."
)

manifest = data.manifest()
checks = data.latest_checks() if data.has_table("audit", "check_results") else pd.DataFrame()
runs = data.latest_model_runs() if data.has_table("audit", "model_runs") else pd.DataFrame()

cols = st.columns(4)
cols[0].metric("Datasets", len(manifest), border=True)
cols[1].metric("Raw rows", f"{int(manifest.row_count.sum()):,}", border=True)
cols[2].metric("Models built", len(runs), border=True)
if checks.empty:
    cols[3].metric("Data tests", "not run yet", border=True)
else:
    counts = checks.status.value_counts()
    cols[3].metric(
        "Data tests passed",
        f"{counts.get('pass', 0)} of {len(checks)}",
        f"{counts.get('warn', 0)} warnings, {counts.get('fail', 0)} failed",
        delta_color="off",
        delta_arrow="off",
        border=True,
    )

st.subheader("Sources")
sources = manifest.assign(
    sha256=manifest.sha256.str[:12],
    fetched_at=manifest.fetched_at.dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M UTC"),
    source_modified=manifest.source_modified.dt.tz_convert("UTC").dt.strftime("%Y-%m-%d"),
)[
    [
        "source_key",
        "title",
        "row_count",
        "fetched_at",
        "source_modified",
        "sha256",
        "page_url",
    ]
]
st.dataframe(
    sources,
    hide_index=True,
    column_config={
        "source_key": "Key",
        "title": "Dataset",
        "row_count": st.column_config.NumberColumn("Rows", format="localized"),
        "fetched_at": "Fetched",
        "source_modified": "Changed on portal",
        "sha256": "SHA-256 (start)",
        "page_url": st.column_config.LinkColumn("Portal page", display_text="open"),
    },
)

st.subheader("Latest data tests")
if checks.empty:
    st.info("No data test results yet. Run `python -m pipeline run` or `python -m pipeline test`.")
else:
    problems = checks[checks.status != "pass"]
    if problems.empty:
        st.success("Every data test passed.")
    else:
        st.markdown(
            "Warnings are known issues in the source data, or sudden month-on-month jumps "
            "that are worth a look and may be real events. They are reported on every run "
            "but do not stop the pipeline; a failed test does."
        )
        st.dataframe(
            problems[["status", "check_name", "message"]],
            hide_index=True,
            column_config={"status": "Status", "check_name": "Test", "message": "Result"},
        )
    with st.expander(f"All {len(checks)} tests"):
        st.dataframe(
            checks[["status", "model", "kind", "column_name", "severity", "message"]],
            hide_index=True,
        )

if not runs.empty:
    st.subheader("Models in the latest build")
    st.dataframe(
        runs[["layer", "model", "materialized", "row_count", "seconds"]].round({"seconds": 3}),
        hide_index=True,
        height=36 * (len(runs) + 1) + 2,
    )
