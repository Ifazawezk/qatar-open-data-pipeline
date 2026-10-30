import pandas as pd
import streamlit as st

from dashboard import charts, data, insights, ui

st.title("Travel and hotels")
st.caption(
    "Passengers at Hamad International Airport (2017 to 2022) and hotel guests and nights "
    "(2019 to 2023). The portal has not published newer months for either series."
)

travel = data.travel()
annual = data.annual()

ui.findings(insights.travel(travel, annual))

airport = travel.dropna(subset=["airport_passengers"])
if not airport.empty:
    fig = charts.lines(
        airport,
        "month_start",
        {"Passengers": "airport_passengers"},
        "Monthly passengers at Hamad International Airport (arrivals plus departures)",
        "Passengers",
    )
    world_cup = pd.Timestamp("2022-11-01")
    if airport.month_start.min() <= world_cup <= airport.month_start.max():
        charts.mark_month(fig, world_cup, "World Cup")
    ui.chart(
        fig,
        airport[
            [
                "month_start",
                "airport_arrivals",
                "airport_departures",
                "airport_passengers",
                "airport_passengers_yoy_pct",
            ]
        ],
        "The FIFA World Cup ran from 20 November to 18 December 2022.",
    )

left, right = st.columns(2)
with left:
    yearly = annual.dropna(subset=["airport_passengers"]).copy()
    if not yearly.empty:
        yearly["year"] = yearly.year.astype(int).astype(str)
        fig = charts.bars(
            yearly,
            "year",
            "airport_passengers",
            "Airport passengers per year",
            "Passengers",
            y_format="~s",
        )
        ui.chart(fig, yearly[["year", "airport_passengers"]])

with right:
    hotels = travel.dropna(subset=["hotel_guests"])
    if not hotels.empty:
        fig = charts.lines(
            hotels,
            "month_start",
            {"Nights of stay": "hotel_nights", "Guests": "hotel_guests"},
            "Hotel guests and nights of stay",
            "Per month",
        )
        ui.chart(
            fig,
            hotels[["month_start", "hotel_guests", "hotel_nights", "nights_per_guest"]],
            "From January 2019 to January 2020 the source has fewer nights than guests, "
            "which is not possible; a data test flags those months.",
        )

ui.sources(
    (
        "Arrivals and departures via Hamad International Airport by month",
        "arrival-and-departures-via-hamad-international-airport-by-month-and-year",
    ),
    (
        "Number of hotel guests and nights of stay by month",
        "number-of-hotel-guests-and-nights-of-stay-by-month",
    ),
)
