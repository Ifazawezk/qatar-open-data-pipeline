import streamlit as st

from dashboard import charts, data, insights, ui

st.title("Electricity and water")
st.caption(
    "KAHRAMAA consumption by official zone. Per-person figures use the average quarterly "
    "population from the Labour Force Survey."
)

national = data.utilities_national()
zones = data.utilities_zones()

ui.findings(insights.utilities(national, zones))

totals = national.copy()
totals["year"] = totals.year.astype(int).astype(str)
left, right = st.columns(2)
with left:
    fig = charts.bars(
        totals,
        "year",
        "electricity_gwh",
        "Electricity consumption",
        "GWh",
        muted=~totals.is_complete_year,
    )
    ui.chart(
        fig,
        totals[["year", "is_complete_year", "electricity_gwh", "electricity_yoy_pct"]],
        "Grey bars are partial years.",
    )
with right:
    fig = charts.bars(
        totals,
        "year",
        "water_million_m3",
        "Water consumption",
        "Million m3",
        value_format=",.1f",
        muted=~totals.is_complete_year,
    )
    ui.chart(
        fig,
        totals[["year", "is_complete_year", "water_million_m3", "water_yoy_pct"]],
        "Grey bars are partial years.",
    )

full = totals[totals.is_complete_year]
left, right = st.columns(2)
with left:
    fig = charts.bars(
        full,
        "year",
        "electricity_kwh_per_capita",
        "Electricity per person",
        "kWh per year",
    )
    ui.chart(fig, full[["year", "avg_population", "electricity_kwh_per_capita"]])
with right:
    fig = charts.bars(
        full,
        "year",
        "water_litres_per_capita_per_day",
        "Water per person",
        "Litres per day",
    )
    ui.chart(fig, full[["year", "avg_population", "water_litres_per_capita_per_day"]])

complete_years = sorted(zones[zones.is_complete_year].year.astype(int).unique())
if complete_years:
    st.subheader("Zones")
    year = st.select_slider("Year", options=complete_years, value=complete_years[-1])
    in_year = zones[zones.year == year]
    top = in_year.nlargest(15, "electricity_kwh").copy()
    top["electricity_gwh"] = top.electricity_kwh / 1e6
    fig = charts.hbars(
        top,
        "zone_label",
        "electricity_gwh",
        f"Top 15 zones by electricity use, {year}",
        "GWh",
        value_format=",.0f",
    )
    ui.chart(
        fig,
        top[["zone_label", "zone_name_ar", "electricity_gwh", "electricity_share_pct"]],
        f"These 15 zones used {top.electricity_share_pct.sum():.0f}% of the electricity in {year}.",
    )

    st.markdown("**One zone over time**")
    labels = zones[["zone_number", "zone_label"]].drop_duplicates().sort_values("zone_number")
    options = dict(zip(labels.zone_number, labels.zone_label, strict=True))
    biggest = int(top.zone_number.iloc[0])
    zone = st.selectbox(
        "Zone",
        list(options),
        index=list(options).index(biggest),
        format_func=options.get,
    )
    history = zones[zones.zone_number == zone].copy()
    history["year"] = history.year.astype(int).astype(str)
    names = history.iloc[0]
    st.caption(f"{names.zone_name_en}  |  {names.zone_name_ar}")
    left, right = st.columns(2)
    history["electricity_gwh"] = history.electricity_kwh / 1e6
    with left:
        fig = charts.bars(
            history,
            "year",
            "electricity_gwh",
            "Electricity",
            "GWh",
            value_format=",.1f",
            muted=~history.is_complete_year,
        )
        ui.chart(
            fig, history[["year", "electricity_gwh", "electricity_rank", "electricity_yoy_pct"]]
        )
    with right:
        fig = charts.bars(
            history,
            "year",
            "water_m3",
            "Water",
            "m3",
            muted=~history.is_complete_year,
            y_format="~s",
        )
        ui.chart(fig, history[["year", "water_m3", "water_share_pct", "water_yoy_pct"]])

ui.sources(
    (
        "Electricity total consumption by zone number",
        "electricity-total-consumption-by-zone-number",
    ),
    ("Water total consumption by zone number", "water-total-consumption-by-zone-number"),
    (
        "Population, area and population density by zone",
        "population-area-and-population-density-per-square-kilometers-by-zone",
    ),
)
