import streamlit as st

from dashboard import charts, data, insights, ui

st.title("Population and jobs")
st.caption("Quarterly Labour Force Survey estimates by sex.")

annual = data.annual()
labour = data.labour()

ui.findings(insights.population(annual) + insights.labour(annual, labour))

by_sex = labour.pivot_table(
    index=["quarter_start", "quarter_label"], columns="sex", values="population"
).reset_index()

left, right = st.columns(2)
with left:
    fig = charts.lines(
        by_sex,
        "quarter_start",
        {"Male": "male", "Female": "female"},
        "Population by sex",
        "People",
    )
    ui.chart(fig, by_sex.drop(columns="quarter_start"))

with right:
    rates = labour.pivot_table(
        index=["quarter_start", "quarter_label"], columns="sex", values="participation_rate_pct"
    ).reset_index()
    fig = charts.lines(
        rates,
        "quarter_start",
        {"Male": "male", "Female": "female", "Total": "total"},
        "Labour force participation, age 15+",
        "% of population 15+",
        value_format=".1f",
        from_zero=False,
    )
    ui.chart(fig, rates.drop(columns="quarter_start"))

growth = annual.dropna(subset=["population_growth_pct"]).copy()
growth["year"] = growth.year.astype(int).astype(str)
left, right = st.columns(2)
with left:
    fig = charts.bars(
        growth,
        "year",
        "population_growth_pct",
        "Population growth on the previous year",
        "%",
        value_format="+.1f",
        y_format=".1f",
    )
    ui.chart(fig, growth[["year", "avg_population", "population_growth_pct"]])

with right:
    unemployment = labour[labour.sex == "total"][
        ["quarter_start", "quarter_label", "unemployed", "unemployment_rate_pct"]
    ]
    fig = charts.lines(
        unemployment,
        "quarter_start",
        {"Unemployment rate": "unemployment_rate_pct"},
        "Unemployment rate",
        "% of labour force",
        value_format=".2f",
        y_format=".2f",
    )
    ui.chart(fig, unemployment.drop(columns="quarter_start"))

ui.sources(("Population and Labor Force by Sex", "population-and-labour-force-by-gender-quarterly"))
