import streamlit as st

from dashboard import charts, data, insights, ui

st.title("Prices")
st.caption("Consumer price index by expenditure group, base year 2018 = 100.")

cpi = data.cpi()
inflation = data.inflation()

ui.findings(insights.prices(inflation))

general = cpi[cpi.is_general_index]
left, right = st.columns(2)
with left:
    fig = charts.lines(
        general,
        "month_start",
        {"General index": "cpi_index"},
        "General consumer price index",
        "Index (2018 = 100)",
        value_format=".2f",
        from_zero=False,
    )
    ui.chart(fig, general[["month_start", "cpi_index", "mom_change_pct", "yoy_change_pct"]])

with right:
    yoy = general.dropna(subset=["yoy_change_pct"])
    fig = charts.bars(
        yoy,
        "month_start",
        "yoy_change_pct",
        "Inflation: change on the same month a year earlier",
        "%",
        value_format="+.2f",
        y_format=".1f",
    )
    ui.chart(fig, yoy[["month_start", "cpi_index", "yoy_change_pct"]])

annual = inflation.dropna(subset=["avg_inflation_pct"])
if not annual.empty:
    order = (
        annual[annual.year == annual.year.max()]
        .sort_values("avg_inflation_pct", ascending=False)
        .group_short_name_en.tolist()
    )
    pivot = annual.pivot_table(
        index="group_short_name_en", columns="year", values="avg_inflation_pct"
    ).reindex(order)
    fig = charts.diverging_heatmap(
        pivot, "Annual inflation by expenditure group (average index change)", "Change"
    )
    ui.chart(
        fig,
        pivot.reset_index().rename(columns={"group_short_name_en": "Group"}),
        "Red is a price rise, blue a fall. Groups are sorted by the latest year.",
    )

st.subheader("Compare a group with the general index")
groups = (
    cpi[~cpi.is_general_index][["group_code", "group_short_name_en", "group_name_ar"]]
    .drop_duplicates()
    .sort_values("group_code")
)
labels = {
    row.group_code: f"{row.group_short_name_en} ({row.group_name_ar})"
    for row in groups.itertuples()
}
choice = st.selectbox("Expenditure group", list(labels), format_func=labels.get)
wide = (
    cpi[cpi.group_code.isin([choice, "000"])]
    .pivot_table(index="month_start", columns="group_code", values="cpi_index")
    .reset_index()
)
name = labels[choice].split(" (")[0]
fig = charts.lines(
    wide,
    "month_start",
    {name: choice, "General index": "000"},
    f"{name} against the general index",
    "Index (2018 = 100)",
    value_format=".2f",
    from_zero=False,
)
ui.chart(fig, wide.rename(columns={choice: name, "000": "General index"}))

ui.sources(
    (
        "Consumer Price Index by Expenditure Group, monthly",
        "consumer-price-index-cpi-by-expenditure-group-monthly",
    ),
)
