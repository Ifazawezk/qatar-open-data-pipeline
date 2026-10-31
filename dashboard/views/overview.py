import pandas as pd
import streamlit as st

from dashboard import charts, data, insights, ui
from dashboard.i18n import tr

st.title(tr("Qatar in numbers"))
st.caption(
    tr(
        "Population, prices, travel and utilities from the Qatar Open Data Portal, "
        "cleaned and tested by this project's pipeline."
    )
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
        tr("{change} on {year}", change=delta(row, prev), year=int(prev.year))
        if prev is not None
        else None,
        delta_color="off",
        border=True,
    )


cols = st.columns(5)
kpi(
    cols[0],
    "avg_population",
    tr("Population"),
    lambda r: tr("{value}M", value=f"{r.avg_population / 1e6:.2f}"),
    lambda r, p: f"{100 * (r.avg_population / p.avg_population - 1):+.1f}%",
)
kpi(
    cols[1],
    "cpi_inflation_pct",
    tr("Inflation"),
    lambda r: f"{r.cpi_inflation_pct:.1f}%",
    lambda r, p: tr("{value} pts", value=f"{r.cpi_inflation_pct - p.cpi_inflation_pct:+.1f}"),
)
kpi(
    cols[2],
    "female_participation_rate_pct",
    tr("Female LFPR"),
    lambda r: f"{r.female_participation_rate_pct:.1f}%",
    lambda r, p: tr(
        "{value} pts",
        value=f"{r.female_participation_rate_pct - p.female_participation_rate_pct:+.1f}",
    ),
)
kpi(
    cols[3],
    "electricity_kwh_per_capita",
    tr("kWh per person"),
    lambda r: f"{r.electricity_kwh_per_capita:,.0f}",
    lambda r, p: f"{100 * (r.electricity_kwh_per_capita / p.electricity_kwh_per_capita - 1):+.1f}%",
)
kpi(
    cols[4],
    "airport_passengers",
    tr("Air passengers"),
    lambda r: tr("{value}M", value=f"{r.airport_passengers / 1e6:.1f}"),
    lambda r, p: f"{100 * (r.airport_passengers / p.airport_passengers - 1):+.0f}%",
)

st.caption(
    tr(
        "Female LFPR: labour force participation rate, the share of women aged 15+ who work or "
        "look for work. kWh per person: electricity use divided by the average population. "
        "Air passengers: arrivals plus departures at Hamad International Airport."
    )
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
    electricity, water, people = tr("Electricity use"), tr("Water use"), tr("Population")
    indexed = pd.DataFrame(
        {
            "year": growth.year.astype(int),
            electricity: 100 * growth.electricity_gwh / base.electricity_gwh,
            water: 100 * growth.water_million_m3 / base.water_million_m3,
            people: 100 * growth.avg_population / base.avg_population,
        }
    )
    fig = charts.lines(
        indexed,
        "year",
        {c: c for c in [electricity, water, people]},
        tr("Utility use and population, indexed to {year} = 100", year=int(base.year)),
        value_format=".1f",
        from_zero=False,
    )
    fig.update_xaxes(dtick=1)
    ui.chart(
        fig,
        indexed,
        tr("When the electricity line is above the population line, use per person is rising."),
    )

st.subheader(tr("Year by year"))
ROWS = [
    (tr("Population, average (millions)"), "avg_population", "{:,.3f}", 1e6),
    (tr("Population growth"), "population_growth_pct", "{:+.1f}%", 1),
    (tr("Labour force participation"), "participation_rate_pct", "{:.1f}%", 1),
    (tr("Female participation"), "female_participation_rate_pct", "{:.1f}%", 1),
    (tr("Unemployment rate"), "unemployment_rate_pct", "{:.2f}%", 1),
    (tr("CPI, average (2018 = 100)"), "cpi_avg_index", "{:.1f}", 1),
    (tr("Inflation"), "cpi_inflation_pct", "{:+.1f}%", 1),
    (tr("Airport passengers (millions)"), "airport_passengers", "{:,.2f}", 1e6),
    (tr("Hotel guests (millions)"), "hotel_guests", "{:,.2f}", 1e6),
    (tr("Hotel nights (millions)"), "hotel_nights", "{:,.2f}", 1e6),
    (tr("Electricity (GWh)"), "electricity_gwh", "{:,.0f}", 1),
    (tr("Electricity per person (kWh)"), "electricity_kwh_per_capita", "{:,.0f}", 1),
    (tr("Water (million m3)"), "water_million_m3", "{:,.1f}", 1),
    (tr("Water per person per day (litres)"), "water_litres_per_capita_per_day", "{:,.0f}", 1),
]


def cells(column: str, fmt: str, scale: float) -> list[str]:
    return [fmt.format(v / scale) if pd.notna(v) else "" for v in annual[column].tolist()]


years = annual.year.astype(int).tolist()
table = pd.DataFrame(
    [[label, *cells(column, fmt, scale)] for label, column, fmt, scale in ROWS],
    columns=[tr("Indicator"), *[str(y) for y in years]],
)
st.dataframe(ui.tidy(table), hide_index=True, height=36 * (len(table) + 1) + 2)
st.caption(tr("An empty cell means the source does not cover that whole year."))
