"""Dashboard tests: the written findings and a headless run of every page."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard import charts, insights, ui

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def annual(**columns):
    return pd.DataFrame({"year": [2021, 2022, 2023], **columns})


def test_population_sentences_use_the_latest_year():
    df = annual(avg_population=[2.5e6, 2.4e6, 2.6e6], population_growth_pct=[1.0, -4.0, 8.3])
    assert insights.population(df) == [
        "Qatar's average population was 2.60 million in 2023, +8.3% on 2022.",
        "The only year-on-year fall in the series was 2022 (-4.0%).",
    ]


def test_findings_are_empty_without_data():
    empty = annual(avg_population=[None] * 3, population_growth_pct=[None] * 3)
    assert insights.population(empty) == []


def test_labour_sentences():
    df = annual(
        female_participation_rate_pct=[50.0, 52.5, 55.25],
        unemployment_rate_pct=[0.1, 0.2, 0.15],
    )
    quarterly = pd.DataFrame(
        {
            "quarter_start": pd.to_datetime(["2023-10-01"] * 3),
            "quarter_label": ["2023-Q4"] * 3,
            "sex": ["male", "female", "total"],
            "population": [750, 250, 1000],
        }
    )
    assert insights.labour(df, quarterly) == [
        "Female labour force participation went from 50.0% in 2021 to 55.2% in 2023 (+5.2 points).",
        "Unemployment stayed between 0.10% and 0.20% in every full year of the survey.",
        "Men are 75% of the population (2023-Q4).",
    ]


def test_travel_sentences_find_the_drop_and_recovery():
    df = annual(airport_passengers=[40e6, 10e6, 30e6])
    monthly = pd.DataFrame(
        {
            "year": [2023, 2023],
            "month_name_en": ["January", "February"],
            "airport_passengers": [2.5e6, 3.1e6],
            "hotel_guests": [None, None],
            "hotel_nights": [None, None],
        }
    )
    assert insights.travel(monthly, df) == [
        "Airport traffic fell from 40.0 million passengers in 2021 to 10.0 million in 2022 "
        "(-75.0%).",
        "By 2023 it was back to 75% of the 2021 level.",
        "The busiest month in the data is February 2023 with 3.10 million passengers.",
    ]


def test_utilities_sentences_skip_partial_years():
    national = pd.DataFrame(
        {
            "year": [2021, 2022, 2023],
            "is_complete_year": [True, True, False],
            "electricity_kwh": [100.0, 110.0, 60.0],
            "electricity_gwh": [1000.0, 1100.0, 600.0],
            "avg_population": [10.0, 10.5, None],
            "electricity_kwh_per_capita": [10.0, 10.476, None],
            "water_litres_per_capita_per_day": [400.0, 410.0, None],
        }
    )
    zones = pd.DataFrame(columns=["year", "electricity_kwh", "electricity_share_pct"])
    assert insights.utilities(national, zones) == [
        "Electricity use grew 10.0% from 2021 to 2022 (1.0 to 1.1 TWh), "
        "while the population grew 5.0%.",
        "In 2022 each resident used about 10 kWh of electricity and 410 litres of water a day.",
        "2023 is a partial year on the portal, so it is left out of growth and per-person figures.",
    ]


def test_charts_refuse_more_than_three_series():
    df = pd.DataFrame({"x": [1, 2], "a": [1, 2], "b": [1, 2], "c": [1, 2], "d": [1, 2]})
    with pytest.raises(ValueError, match="at most three"):
        charts.lines(df, "x", {k: k for k in "abcd"}, "too many")


def test_tidy_rounds_floats_and_shows_dates():
    df = pd.DataFrame({"when": pd.to_datetime(["2024-01-01"]), 2024: [1.23456]})
    out = ui.tidy(df)
    assert list(out.columns) == ["when", "2024"]
    assert out.iloc[0, 1] == 1.23
    assert str(out.iloc[0, 0]) == "2024-01-01"


@pytest.fixture
def app(fixture_settings, warehouse, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(fixture_settings.warehouse_path))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


PAGES = ["views/population.py", "views/prices.py"]


def test_overview_renders_kpis_from_the_warehouse(app):
    assert not app.exception
    assert app.title[0].value == "Qatar in numbers"
    labels = [m.label for m in app.metric]
    assert "Population (2025)" in labels


@pytest.mark.parametrize("page", PAGES)
def test_every_page_runs_without_errors(app, page):
    app.switch_page(page).run()
    assert not app.exception, [e.message for e in app.exception]


def test_missing_warehouse_shows_a_helpful_error(tmp_path, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(tmp_path / "nothing.duckdb"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert "python -m pipeline run" in at.error[0].value
