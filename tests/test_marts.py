"""Mart models checked against values recomputed in Python from the fixture CSVs."""

import csv
from collections import defaultdict
from datetime import date

import pytest

from conftest import FIXTURES


def fixture_rows(key):
    with (FIXTURES / "raw" / f"{key}.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def one(con, sql):
    return con.execute(sql).fetchone()


def population(year, quarter, sex=None, indicator="Population"):
    total = 0
    for r in fixture_rows("population_labour_force"):
        if (
            r["year"] == str(year)
            and r["quarter"] == f"Q{quarter}"
            and r["indicator"] == indicator
            and (sex is None or r["gender"] == sex)
        ):
            total += int(r["number"])
    return total


def test_labour_total_rows_add_up_and_rates_are_correct(warehouse):
    pop, active, unemployed, part, unemp = one(
        warehouse,
        """
        select population, economically_active, unemployed,
               participation_rate_pct, unemployment_rate_pct
        from marts.fct_labour_market_quarterly
        where quarter_label = '2025-Q3' and sex = 'total'
        """,
    )
    expected_active = population(2025, 3, indicator="Economically Active")
    expected_employed = population(2025, 3, indicator="Employed")
    expected_15 = population(2025, 3, indicator="Population (15 Years & above)")

    assert pop == population(2025, 3)
    assert active == expected_active
    assert unemployed == expected_active - expected_employed
    assert part == pytest.approx(100 * expected_active / expected_15)
    assert unemp == pytest.approx(100 * (expected_active - expected_employed) / expected_active)


def test_population_growth_compares_same_quarter_last_year(warehouse):
    [growth] = one(
        warehouse,
        "select population_yoy_pct from marts.fct_labour_market_quarterly "
        "where quarter_label = '2025-Q3' and sex = 'female'",
    )
    expected = population(2025, 3, "Females") / population(2024, 3, "Females") - 1
    assert growth == pytest.approx(100 * expected)
    [first_year] = one(
        warehouse,
        "select count(population_yoy_pct) from marts.fct_labour_market_quarterly where year = 2024",
    )
    assert first_year == 0


def test_cpi_changes(warehouse):
    yoy, mom = one(
        warehouse,
        "select yoy_change_pct, mom_change_pct from marts.fct_cpi_monthly "
        "where group_code = '000' and month_start = date '2021-01-01'",
    )
    assert yoy == pytest.approx(100 * (97.11 / 98.38 - 1))
    assert mom is not None
    [first_month] = one(
        warehouse,
        "select mom_change_pct from marts.fct_cpi_monthly "
        "where group_code = '000' and month_start = date '2020-01-01'",
    )
    assert first_month is None


def test_annual_inflation_uses_twelve_month_averages(warehouse):
    by_year = defaultdict(list)
    for r in fixture_rows("cpi_monthly"):
        if r["group_code"] == "0":
            by_year[int(r["year"])].append(float(r["cpi_index"]))
    expected = sum(by_year[2021]) / 12 / (sum(by_year[2020]) / 12) - 1

    rows = warehouse.execute(
        "select year, months_reported, avg_inflation_pct from marts.fct_inflation_annual "
        "where group_code = '000' order by year"
    ).fetchall()
    assert rows[0] == (2020, 12, None)
    assert rows[1][:2] == (2021, 12)
    assert rows[1][2] == pytest.approx(100 * expected)


def test_travel_month_combines_airport_and_hotels(warehouse):
    row = one(
        warehouse,
        """
        select airport_arrivals, airport_departures, airport_passengers,
               hotel_guests, hotel_nights, nights_per_guest, month_name_ar
        from marts.fct_travel_monthly where month_start = date '2022-12-01'
        """,
    )
    assert row[:5] == (1704952, 1916866, 1704952 + 1916866, 602481, 1021211)
    assert row[5] == pytest.approx(1021211 / 602481)
    assert row[6] == "ديسمبر"


def test_travel_only_keeps_months_with_data(warehouse):
    first, last, months = one(
        warehouse,
        "select min(month_start), max(month_start), count(*) from marts.fct_travel_monthly",
    )
    assert (first, last, months) == (date(2021, 1, 1), date(2022, 12, 1), 24)


def test_partial_utility_year_is_flagged_and_not_compared(warehouse):
    rows = warehouse.execute(
        """
        select year, is_complete_year, electricity_kwh_per_capita, electricity_yoy_pct
        from marts.fct_utilities_national_annual order by year
        """
    ).fetchall()
    assert [(r[0], r[1]) for r in rows] == [(2024, True), (2025, True), (2026, False)]
    assert rows[0][3] is None  # no 2023 to compare with
    assert rows[1][3] is not None
    assert rows[2][2] is None and rows[2][3] is None


def test_per_capita_uses_average_quarterly_population(warehouse):
    kwh_2024 = sum(
        int(r["value"]) for r in fixture_rows("electricity_by_zone") if r["year"] == "2024"
    )
    avg_pop_2024 = sum(population(2024, q) for q in range(1, 5)) / 4
    [per_capita] = one(
        warehouse,
        "select electricity_kwh_per_capita from marts.fct_utilities_national_annual "
        "where year = 2024",
    )
    assert per_capita == pytest.approx(kwh_2024 / avg_pop_2024)


def test_zone_shares_add_up_to_100(warehouse):
    rows = warehouse.execute(
        "select year, sum(electricity_share_pct), sum(water_share_pct) "
        "from marts.fct_utilities_zone_annual group by year"
    ).fetchall()
    for _, electricity, water in rows:
        assert electricity == pytest.approx(100)
        assert water == pytest.approx(100)


def test_zone_labels_are_short(warehouse):
    labels = dict(
        warehouse.execute("select zone_number, zone_label from marts.dim_zone").fetchall()
    )
    assert labels[1] == "Zone 1: Al Jasra"
    assert labels[70] == "Zone 70: Leabaib and others"


def test_annual_indicators_only_use_full_years(warehouse):
    rows = {
        r[0]: r[1:]
        for r in warehouse.execute(
            "select year, avg_population, cpi_inflation_pct, airport_passengers, "
            "electricity_gwh from marts.mart_annual_indicators"
        ).fetchall()
    }
    assert sorted(rows) == [2020, 2021, 2022, 2024, 2025]
    passengers_2022 = sum(
        int(r["total"]) for r in fixture_rows("hia_passengers") if r["year"] == "2022"
    )
    assert rows[2022][2] == passengers_2022
    assert rows[2021][1] is not None  # inflation needs 2020 and 2021
    assert rows[2020][1] is None
    assert rows[2025][0] == pytest.approx(sum(population(2025, q) for q in range(1, 5)) / 4)
