import pandas as pd
import streamlit as st

from dashboard import charts, data, insights, ui

st.title("Qatar in numbers")
st.caption(
    "Population, prices, travel and utilities from the Qatar Open Data Portal, "
    "cleaned and tested by this project's pipeline."
)

annual = data.annual()


def kpi(slot, column: str, label: str, value, delta) -> None:
    """Latest full year of `column`, compared with the year before it."""
    rows = annual.dropna(subset=[column]).sort_values("year")
    if rows.empty:
        return
    row = rows.iloc[-1]
    prev = rows.iloc[-2] if len(rows) > 1 else None
    slot.metric(
        f"{label} ({int(row.year)})",
        value(row),
        f"{delta(row, prev)} on {int(prev.year)}" if prev is not None else None,
        delta_color="off",
        border=True,
    )


cols = st.columns(5)
kpi(
    cols[0],
    "avg_population",
    "Population",
    lambda r: f"{r.avg_population / 1e6:.2f}M",
    lambda r, p: f"{100 * (r.avg_population / p.avg_population - 1):+.1f}%",
)
kpi(
    cols[1],
    "cpi_inflation_pct",
    "Inflation",
    lambda r: f"{r.cpi_inflation_pct:.1f}%",
    lambda r, p: f"{r.cpi_inflation_pct - p.cpi_inflation_pct:+.1f} pts",
)
kpi(
    cols[2],
    "female_participation_rate_pct",
    "Female LFPR",
    lambda r: f"{r.female_participation_rate_pct:.1f}%",
    lambda r, p: f"{r.female_participation_rate_pct - p.female_participation_rate_pct:+.1f} pts",
)
kpi(
    cols[3],
    "electricity_kwh_per_capita",
    "kWh per person",
    lambda r: f"{r.electricity_kwh_per_capita:,.0f}",
    lambda r, p: f"{100 * (r.electricity_kwh_per_capita / p.electricity_kwh_per_capita - 1):+.1f}%",
)
kpi(
    cols[4],
    "airport_passengers",
    "Air passengers",
    lambda r: f"{r.airport_passengers / 1e6:.1f}M",
    lambda r, p: f"{100 * (r.airport_passengers / p.airport_passengers - 1):+.0f}%",
)

st.caption(
    "Female LFPR: labour force participation rate, the share of women aged 15+ who work or "
    "look for work. kWh per person: electricity use divided by the average population. "
    "Air passengers: arrivals plus departures at Hamad International Airport."
)

ui.findings(
    [
        *insights.population(annual)[:1],
        *insights.labour(annual, data.labour())[:1],
        *insights.prices(data.inflation())[:1],
        *insights.travel(data.travel(), annual)[:1],
        *insights.utilities(data.utilities_national(), data.utilities_zones())[:1],
    ]
)

# Growth compared on one axis: each series indexed to its first common year.
growth = annual.dropna(subset=["avg_population", "electricity_gwh", "water_million_m3"])
if len(growth) >= 2:
    base = growth.iloc[0]
    indexed = pd.DataFrame(
        {
            "year": growth.year.astype(int),
            "Electricity use": 100 * growth.electricity_gwh / base.electricity_gwh,
            "Water use": 100 * growth.water_million_m3 / base.water_million_m3,
            "Population": 100 * growth.avg_population / base.avg_population,
        }
    )
    fig = charts.lines(
        indexed,
        "year",
        {c: c for c in ["Electricity use", "Water use", "Population"]},
        f"Utility use and population, indexed to {int(base.year)} = 100",
        value_format=".1f",
        from_zero=False,
    )
    fig.update_xaxes(dtick=1)
    ui.chart(
        fig,
        indexed,
        "When the electricity line is above the population line, use per person is rising.",
    )

st.subheader("Year by year")
ROWS = [
    ("Population, average (millions)", "avg_population", "{:,.3f}"),
    ("Population growth", "population_growth_pct", "{:+.1f}%"),
    ("Labour force participation", "participation_rate_pct", "{:.1f}%"),
    ("Female participation", "female_participation_rate_pct", "{:.1f}%"),
    ("Unemployment rate", "unemployment_rate_pct", "{:.2f}%"),
    ("CPI, average (2018 = 100)", "cpi_avg_index", "{:.1f}"),
    ("Inflation", "cpi_inflation_pct", "{:+.1f}%"),
    ("Airport passengers (millions)", "airport_passengers", "{:,.2f}"),
    ("Hotel guests (millions)", "hotel_guests", "{:,.2f}"),
    ("Hotel nights (millions)", "hotel_nights", "{:,.2f}"),
    ("Electricity (GWh)", "electricity_gwh", "{:,.0f}"),
    ("Electricity per person (kWh)", "electricity_kwh_per_capita", "{:,.0f}"),
    ("Water (million m3)", "water_million_m3", "{:,.1f}"),
    ("Water per person per day (litres)", "water_litres_per_capita_per_day", "{:,.0f}"),
]


def cells(label: str, column: str, fmt: str) -> list[str]:
    scale = 1e6 if "(millions)" in label else 1
    return [fmt.format(v / scale) if pd.notna(v) else "" for v in annual[column].tolist()]


years = annual.year.astype(int).tolist()
table = pd.DataFrame(
    [[label, *cells(label, column, fmt)] for label, column, fmt in ROWS],
    columns=["Indicator", *[str(y) for y in years]],
)
st.dataframe(table, hide_index=True)
st.caption("An empty cell means the source does not cover that whole year.")
