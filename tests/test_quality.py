from datetime import date

import pytest

from conftest import make_catalogue, stage_fixture_files, write_raw
from pipeline.build import build_warehouse
from pipeline.cli import main
from pipeline.config import PROJECT_ROOT
from pipeline.quality import (
    DataQualityError,
    QualityConfigError,
    build_checks,
    load_schema,
    run_checks,
)
from pipeline.transform import discover, run_models
from pipeline.warehouse import connect

TODAY = date(2026, 10, 2)


@pytest.fixture
def mini(tmp_path):
    """Two tiny models with deliberate problems, built in memory."""
    models_dir = tmp_path / "models"
    (models_dir / "staging").mkdir(parents=True)
    (models_dir / "marts").mkdir(parents=True)
    (models_dir / "staging" / "stg_items.sql").write_text(
        """
        select * from (values
            (1, 'a', 10, date '2026-09-30', 5, 4),
            (2, 'b', 20, date '2026-09-01', 5, 6),
            (2, 'z', null, date '2026-08-01', null, 1)
        ) t(id, code, amount, day, guests, nights)
        """,
        encoding="utf-8",
    )
    (models_dir / "marts" / "dim_codes.sql").write_text(
        "select * from (values ('a'), ('b')) t(code)", encoding="utf-8"
    )
    con = connect(":memory:")
    models = discover(models_dir)
    run_models(con, models)
    return con, models


def statuses(con, models, schema, today=TODAY):
    results = run_checks(con, build_checks(schema, models, today))
    return {r.name: (r.status, r.message) for r in results}


def col(name, *tests):
    return {"name": name, "tests": list(tests)}


def test_column_checks(mini):
    con, models = mini
    schema = {
        "models": [
            {
                "name": "stg_items",
                "columns": [
                    col("id", "not_null", "unique"),
                    col("amount", "not_null", {"range": {"min": 0, "max": 15}}),
                    col("code", {"accepted_values": {"values": ["a", "b"], "severity": "warn"}}),
                    col("code", {"relationships": {"to": "dim_codes", "field": "code"}}),
                ],
            }
        ]
    }
    got = statuses(con, models, schema)
    assert got["not_null.stg_items.id"] == ("pass", "ok")
    assert got["unique.stg_items.id"] == ("fail", "1 duplicated values")
    assert got["not_null.stg_items.amount"] == ("fail", "1 null values")
    assert got["range.stg_items.amount"] == ("fail", "1 rows outside [0, 15]")
    assert got["accepted_values.stg_items.code"][0] == "warn"
    assert got["relationships.stg_items.code"] == (
        "fail",
        "1 rows without a match in dim_codes.code",
    )


def test_model_checks(mini):
    con, models = mini
    schema = {
        "models": [
            {
                "name": "stg_items",
                "tests": [
                    {"unique": ["id", "code"]},
                    {"row_count": {"min": 5}},
                    {"expression": {"name": "nights_ge_guests", "sql": "nights >= guests"}},
                    {
                        "query": {
                            "name": "codes_known",
                            "sql": "select code from {{ ref('stg_items') }} "
                            "except select code from {{ ref('dim_codes') }}",
                        }
                    },
                ],
            }
        ]
    }
    got = statuses(con, models, schema)
    assert got["unique.stg_items.id+code"] == ("pass", "ok")
    assert got["row_count.stg_items.table"] == ("fail", "3 rows (expected 5 to any)")
    # id 1 fails (4 nights, 5 guests); the row with NULL guests is skipped, not failed
    assert got["expression.stg_items.nights_ge_guests"][1] == (
        "1 rows where not (nights >= guests)"
    )
    assert got["query.stg_items.codes_known"] == ("fail", "1 rows returned")


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 10, 5), "pass"),
        (date(2026, 10, 20), "warn"),
        (date(2026, 12, 1), "fail"),
    ],
)
def test_freshness_thresholds(mini, today, expected):
    con, models = mini
    schema = {
        "models": [
            {
                "name": "stg_items",
                "tests": [
                    {"freshness": {"column": "day", "warn_after_days": 10, "error_after_days": 40}}
                ],
            }
        ]
    }
    [(status, message)] = statuses(con, models, schema, today).values()
    assert status == expected
    assert "latest day is 2026-09-30" in message


def test_unknown_names_are_config_errors(mini):
    _, models = mini
    with pytest.raises(QualityConfigError, match="unknown model 'nope'"):
        build_checks({"models": [{"name": "nope"}]}, models, TODAY)
    with pytest.raises(QualityConfigError, match="unknown check 'sometimes'"):
        build_checks(
            {"models": [{"name": "stg_items", "columns": [col("id", "sometimes")]}]},
            models,
            TODAY,
        )


def test_project_schema_matches_the_models():
    models = discover(PROJECT_ROOT / "models")
    checks = build_checks(load_schema(PROJECT_ROOT / "models" / "schema.yml"), models, TODAY)
    assert len(checks) > 80
    tested = {c.model for c in checks}
    assert set(models) <= tested, f"models without tests: {set(models) - tested}"


def test_fixture_data_only_fails_volume_checks(warehouse):
    """The fixtures are cut down on purpose, so only row counts and coverage fail."""
    models = discover(PROJECT_ROOT / "models")
    checks = build_checks(load_schema(PROJECT_ROOT / "models" / "schema.yml"), models, TODAY)
    failed = {r.name for r in run_checks(warehouse, checks) if r.status == "fail"}
    assert failed == {
        "row_count.stg_population_labour_force.table",
        "row_count.stg_cpi_monthly.table",
        "row_count.stg_hia_passengers.table",
        "row_count.stg_hotel_guests_nights.table",
        "row_count.stg_electricity_by_zone.table",
        "row_count.stg_water_by_zone.table",
        "query.stg_cpi_monthly.every_month_has_all_groups",
        "expression.fct_utilities_national_annual.most_zones_reported",
        # fixture CPI stops in December 2021
        "freshness.fct_cpi_monthly.month_start",
    }


def _tiny_project(settings):
    models = settings.root / "models" / "staging"
    models.mkdir(parents=True)
    (models / "stg_trips.sql").write_text(
        "select year::int as year, total::int as total from {{ source('trips') }}",
        encoding="utf-8",
    )
    (settings.root / "models" / "schema.yml").write_text(
        "models:\n"
        "  - name: stg_trips\n"
        "    columns:\n"
        "      - name: total\n"
        "        tests: [not_null, {range: {min: 0}}]\n",
        encoding="utf-8",
    )


def test_failed_data_test_rolls_back_but_is_recorded(settings):
    _tiny_project(settings)
    catalogue = make_catalogue("trips")
    write_raw(settings, "trips", b"year,total\n2022,10\n")
    build_warehouse(settings, catalogue, run_tests=True, today=TODAY)

    write_raw(settings, "trips", b"year,total\n2022,10\n2023,-5\n")
    with pytest.raises(DataQualityError, match="range.stg_trips.total"):
        build_warehouse(settings, catalogue, run_tests=True, today=TODAY)

    con = connect(settings.warehouse_path, read_only=True)
    assert con.execute("select count(*) from staging.stg_trips").fetchone() == (1,)
    statuses_by_run = con.execute(
        "select status, count(*) from audit.check_results "
        "where check_name = 'range.stg_trips.total' group by status order by status"
    ).fetchall()
    assert statuses_by_run == [("fail", 1), ("pass", 1)]
    con.close()


def test_cli_run_fails_loudly_on_bad_data(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("QODP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("QODP_WAREHOUSE", raising=False)
    from pipeline.config import Settings

    stage_fixture_files(Settings.from_env())
    assert main(["run", "--skip-extract"]) == 1
    err = capsys.readouterr().err
    assert "DATA QUALITY FAILED" in err
    assert "row_count.stg_cpi_monthly.table" in err
