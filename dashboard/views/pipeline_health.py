import pandas as pd
import streamlit as st

from dashboard import data
from dashboard.i18n import tr

st.title(tr("Pipeline health"))
st.caption(
    tr(
        "Where the data came from, when it was fetched, and how the latest data tests went. "
        "The full data catalog with lineage is in docs/data_catalog.md."
    )
)

manifest = data.manifest()
checks = data.latest_checks() if data.has_table("audit", "check_results") else pd.DataFrame()
runs = data.latest_model_runs() if data.has_table("audit", "model_runs") else pd.DataFrame()

cols = st.columns(4)
cols[0].metric(tr("Datasets"), len(manifest), border=True)
cols[1].metric(tr("Raw rows"), f"{int(manifest.row_count.sum()):,}", border=True)
cols[2].metric(tr("Models built"), len(runs), border=True)
if checks.empty:
    cols[3].metric(tr("Data tests"), tr("not run yet"), border=True)
else:
    counts = checks.status.value_counts()
    cols[3].metric(
        tr("Data tests passed"),
        tr("{passed} of {total}", passed=counts.get("pass", 0), total=len(checks)),
        tr(
            "{warnings} warnings, {failed} failed",
            warnings=counts.get("warn", 0),
            failed=counts.get("fail", 0),
        ),
        delta_color="off",
        delta_arrow="off",
        border=True,
    )

st.subheader(tr("Sources"))
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
        "source_key": tr("Key"),
        "title": tr("Dataset"),
        "row_count": st.column_config.NumberColumn(tr("Rows"), format="localized"),
        "fetched_at": tr("Fetched"),
        "source_modified": tr("Changed on portal"),
        "sha256": tr("SHA-256 (start)"),
        "page_url": st.column_config.LinkColumn(tr("Portal page"), display_text=tr("open")),
    },
)

st.subheader(tr("Latest data tests"))
if checks.empty:
    st.info(
        tr("No data test results yet. Run `python -m pipeline run` or `python -m pipeline test`.")
    )
else:
    problems = checks[checks.status != "pass"]
    if problems.empty:
        st.success(tr("Every data test passed."))
    else:
        st.markdown(
            tr(
                "Warnings are known issues in the source data, or sudden month-on-month jumps "
                "that are worth a look and may be real events. They are reported on every run "
                "but do not stop the pipeline; a failed test does."
            )
        )
        st.dataframe(
            problems[["status", "check_name", "message"]],
            hide_index=True,
            column_config={
                "status": tr("Status"),
                "check_name": tr("Test"),
                "message": tr("Result"),
            },
        )
    with st.expander(tr("All {count} tests", count=len(checks))):
        st.dataframe(
            checks[["status", "model", "kind", "column_name", "severity", "message"]],
            hide_index=True,
        )

if not runs.empty:
    st.subheader(tr("Models in the latest build"))
    st.dataframe(
        runs[["layer", "model", "materialized", "row_count", "seconds"]].round({"seconds": 3}),
        hide_index=True,
        height=36 * (len(runs) + 1) + 2,
    )
