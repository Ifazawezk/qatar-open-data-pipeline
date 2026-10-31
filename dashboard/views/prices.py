import streamlit as st

from dashboard import charts, data, insights, ui
from dashboard.i18n import is_arabic, localised, tr

st.title(tr("Prices"))
st.caption(tr("Consumer price index by expenditure group, base year 2018 = 100."))

cpi = data.cpi()
inflation = data.inflation()

ui.findings(insights.prices(inflation))

group_name = localised("group_short_name_en", "group_name_ar")
general = cpi[cpi.is_general_index]
general_name = tr("General index")
left, right = st.columns(2)
with left:
    fig = charts.lines(
        general,
        "month_start",
        {general_name: "cpi_index"},
        tr("General consumer price index"),
        tr("Index (2018 = 100)"),
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
        tr("Inflation: change on the same month a year earlier"),
        "%",
        value_format="+.2f",
        y_format=".1f",
    )
    ui.chart(fig, yoy[["month_start", "cpi_index", "yoy_change_pct"]])

annual = inflation.dropna(subset=["avg_inflation_pct"])
if not annual.empty:
    order = (
        annual[annual.year == annual.year.max()]
        .sort_values("avg_inflation_pct", ascending=False)[group_name]
        .tolist()
    )
    pivot = annual.pivot_table(
        index=group_name, columns="year", values="avg_inflation_pct"
    ).reindex(order)
    fig = charts.diverging_heatmap(
        pivot, tr("Annual inflation by expenditure group (average index change)"), tr("Change")
    )
    ui.chart(
        fig,
        pivot.reset_index().rename(columns={group_name: tr("Group")}),
        tr("Red is a price rise, blue a fall. Groups are sorted by the latest year."),
    )

st.subheader(tr("Compare a group with the general index"))
groups = (
    cpi[~cpi.is_general_index][["group_code", "group_short_name_en", "group_name_ar"]]
    .drop_duplicates()
    .sort_values("group_code")
)
names = {row.group_code: row.group_short_name_en for row in groups.itertuples()}
names_ar = {row.group_code: row.group_name_ar for row in groups.itertuples()}
first, second = (names_ar, names) if is_arabic() else (names, names_ar)
choice = st.selectbox(
    tr("Expenditure group"),
    list(names),
    format_func=lambda code: f"{first[code]} ({second[code]})",
    key="group",
)
wide = (
    cpi[cpi.group_code.isin([choice, "000"])]
    .pivot_table(index="month_start", columns="group_code", values="cpi_index")
    .reset_index()
)
name = first[choice]
fig = charts.lines(
    wide,
    "month_start",
    {name: choice, general_name: "000"},
    tr("{name} against the general index", name=name),
    tr("Index (2018 = 100)"),
    value_format=".2f",
    from_zero=False,
)
ui.chart(fig, wide.rename(columns={choice: name, "000": general_name}))

ui.sources(
    (
        tr("Consumer Price Index by Expenditure Group, monthly"),
        "consumer-price-index-cpi-by-expenditure-group-monthly",
    ),
)
