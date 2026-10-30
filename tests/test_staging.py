"""Staging models run against trimmed copies of the real portal files."""

from datetime import date

import pytest

STAGING = [
    "stg_population_labour_force",
    "stg_cpi_monthly",
    "stg_hia_passengers",
    "stg_hotel_guests_nights",
    "stg_electricity_by_zone",
    "stg_water_by_zone",
    "stg_zones",
]


def rows(con, sql):
    return con.execute(sql).fetchall()


@pytest.mark.parametrize("model", STAGING)
def test_every_staging_column_is_parsed(warehouse, model):
    """try_cast returns NULL on bad input, so a NULL anywhere means a parsing gap."""
    columns = [c[0] for c in rows(warehouse, f"describe staging.{model}")]
    checks = ", ".join(f"count(*) filter (where {c} is null)" for c in columns)
    counts = rows(warehouse, f"select {checks} from staging.{model}")[0]
    nulls = dict(zip(columns, counts, strict=True))
    assert all(v == 0 for v in nulls.values()), nulls


def test_staging_keeps_every_raw_row(warehouse):
    for model, source in [
        ("stg_population_labour_force", "population_labour_force"),
        ("stg_cpi_monthly", "cpi_monthly"),
        ("stg_hia_passengers", "hia_passengers"),
        ("stg_hotel_guests_nights", "hotel_guests_nights"),
        ("stg_electricity_by_zone", "electricity_by_zone"),
        ("stg_water_by_zone", "water_by_zone"),
    ]:
        staged = rows(warehouse, f"select count(*) from staging.{model}")
        raw = rows(warehouse, f"select count(*) from raw.{source}")
        assert staged == raw, model


def test_cpi_codes_months_and_names_are_cleaned(warehouse):
    result = rows(
        warehouse,
        """
        select month_start, group_code, group_name_en, is_general_index, cpi_index
        from staging.stg_cpi_monthly
        where year = 2020 and month = 1
        order by group_code
        """,
    )
    assert result == [
        (date(2020, 1, 1), "000", "General index", True, 98.38),
        (date(2020, 1, 1), "001", "Food and beverages", False, 100.42),
        (date(2020, 1, 1), "002", "Tobacco", False, 227.0),
    ]


def test_cpi_arabic_names_have_single_spaces(warehouse):
    names = rows(warehouse, "select distinct group_name_ar from staging.stg_cpi_monthly")
    assert all("  " not in name for (name,) in names)


def test_hotel_year_and_measure_are_split(warehouse):
    result = rows(
        warehouse,
        """
        select measure, measure_ar, value
        from staging.stg_hotel_guests_nights
        where month_start = date '2022-12-01'
        order by measure
        """,
    )
    assert result == [("guests", "الضيوف", 602481), ("nights", "ليالي", 1021211)]


def test_hotel_covers_every_month_once_per_measure(warehouse):
    result = rows(
        warehouse,
        """
        select year, measure, count(distinct month)
        from staging.stg_hotel_guests_nights
        group by all order by all
        """,
    )
    assert result == [
        (2021, "guests", 12),
        (2021, "nights", 12),
        (2022, "guests", 12),
        (2022, "nights", 12),
    ]


def test_airport_months_and_directions(warehouse):
    result = rows(
        warehouse,
        """
        select direction, passengers from staging.stg_hia_passengers
        where month_start = date '2022-12-01' order by direction
        """,
    )
    assert result == [("arrivals", 1704952), ("departures", 1916866)]


def test_population_labels_map_to_codes(warehouse):
    result = dict(
        rows(
            warehouse,
            """
            select indicator, persons from staging.stg_population_labour_force
            where quarter_label = '2025-Q3' and sex = 'female'
            """,
        )
    )
    assert result == {
        "population": 952971,
        "population_15_plus": 676216,
        "economically_active": 446920,
        "economically_inactive": 229296,
        "employed": 445368,
    }
    assert rows(
        warehouse,
        "select distinct quarter_start from staging.stg_population_labour_force "
        "where quarter_label = '2025-Q3'",
    ) == [(date(2025, 7, 1),)]


def test_zone_names_are_one_row_per_zone(warehouse):
    result = rows(
        warehouse,
        "select zone_number, zone_name_en, zone_name_ar from staging.stg_zones order by 1",
    )
    assert [r[0] for r in result] == [1, 2, 69, 70]
    assert result[0][1:] == ("Al Jasra", "الجسرة")


def test_utility_values_are_integers(warehouse):
    assert rows(
        warehouse,
        "select electricity_kwh from staging.stg_electricity_by_zone "
        "where year = 2024 and zone_number = 70",
    ) == [(2719293807,)]
    assert rows(
        warehouse,
        "select water_m3 from staging.stg_water_by_zone where year = 2025 and zone_number = 1",
    ) == [(340687,)]
