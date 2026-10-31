"""The anomaly check: warnings about sudden month-on-month jumps."""

from datetime import date

import pytest

from conftest import make_catalogue, write_raw
from pipeline.build import build_warehouse
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
LIMITS = {"defaults": {"max_change_pct": 40, "typical_multiple": 3, "min_history_months": 12}}


def months(values, group="a", start=(2023, 1)):
    """(YYYY-MM, group, value) rows for consecutive months; None leaves a NULL value."""
    year, month = start
    rows = []
    for value in values:
        rows.append((f"{year}-{month:02d}", group, value))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return rows


def project(tmp_path, rows, time_column="month_start"):
    """A one-table project with a time column, grp and value."""
    folder = tmp_path / "models" / "staging"
    folder.mkdir(parents=True)
    values = ", ".join(
        f"(date '{month}-01', '{group}', {'null::double' if value is None else value})"
        for month, group, value in rows
    )
    (folder / "stg_series.sql").write_text(
        f"select * from (values {values}) t({time_column}, grp, value)", encoding="utf-8"
    )
    con = connect(":memory:")
    models = discover(tmp_path / "models")
    run_models(con, models)
    return con, models


def schema(test="anomaly", limits=None):
    return {
        "models": [{"name": "stg_series", "columns": [{"name": "value", "tests": [test]}]}],
        "limits": {"anomaly": LIMITS if limits is None else limits},
    }


def run(con, models, test="anomaly", limits=None):
    [result] = run_checks(con, build_checks(schema(test, limits), models, TODAY))
    return result


CALM = [100, 105] * 6  # moves about 5% every month


def test_jumps_up_and_down_give_a_warning_that_names_the_months(tmp_path):
    con, models = project(tmp_path, months([*CALM, 200, 100]))
    result = run(con, models)
    assert result.name == "anomaly.stg_series.value"
    assert result.status == "warn"
    assert result.message == (
        "2 months moved more than 40% on the previous month: 2024-01 +90.5%, 2024-02 -50.0%"
    )


def test_a_calm_series_passes(tmp_path):
    con, models = project(tmp_path, months(CALM))
    result = run(con, models)
    assert (result.status, result.message) == ("pass", "no month moved more than 40%")


def test_one_flagged_month_reads_as_singular(tmp_path):
    con, models = project(tmp_path, months([*CALM, 200]))
    assert run(con, models).message.startswith("1 month moved more than 40%")


def test_a_move_of_exactly_the_limit_is_not_flagged(tmp_path):
    con, models = project(tmp_path, months([100, 150]))
    limits = {"defaults": {**LIMITS["defaults"], "max_change_pct": 50}}
    assert run(con, models, limits=limits).status == "pass"


def test_months_are_compared_on_the_calendar_not_by_row_position(tmp_path):
    rows = months([100, 105, 100], start=(2023, 1)) + months([300, 310], start=(2023, 7))
    con, models = project(tmp_path, rows)
    assert run(con, models).status == "pass"


def test_missing_values_do_not_count_as_a_previous_month(tmp_path):
    con, models = project(tmp_path, months([100, 105, None, 300, 310]))
    assert run(con, models).status == "pass"


def test_a_previous_value_of_zero_is_skipped(tmp_path):
    con, models = project(tmp_path, months([100, 105, 0, 300, 310]))
    result = run(con, models)
    assert result.status == "warn"  # the fall to zero is a real jump
    assert result.message.endswith(": 2023-03 -100.0%")  # and 0 to 300 has no percentage


def test_series_in_one_table_are_compared_separately(tmp_path):
    rows = months(CALM, "a") + months(CALM, "b")
    rows += [("2024-01", "a", 100), ("2024-01", "b", 300)]
    rows = [(m, g, v * 10 if g == "b" else v) for m, g, v in rows]
    con, models = project(tmp_path, rows)
    result = run(con, models, {"anomaly": {"by": "grp"}})
    assert result.message.endswith(": b 2024-01 +185.7%")


def test_a_naturally_jumpy_series_needs_more_than_the_percentage(tmp_path):
    jumpy = [100, 160] * 8  # moves over 40% every month, so that is normal for it
    con, models = project(tmp_path, months(jumpy))
    assert run(con, models).status == "pass"

    con, models = project(tmp_path / "bigger", months([*jumpy, 2000]))
    assert run(con, models).message.endswith(": 2024-05 +1150.0%")


def test_a_series_that_never_moves_is_flagged_on_its_first_move(tmp_path):
    con, models = project(tmp_path, months([100] * 15 + [150]))
    assert run(con, models).message.endswith(": 2024-04 +50.0%")


def test_a_short_series_uses_only_the_percentage(tmp_path):
    # The median of two changes is too unreliable to hide a tripled value.
    con, models = project(tmp_path, months([100, 110, 300]))
    assert run(con, models).message.endswith(": 2023-03 +172.7%")


def test_time_column_can_be_named(tmp_path):
    con, models = project(tmp_path, months([*CALM, 200]), time_column="period")
    assert run(con, models, {"anomaly": {"time_column": "period"}}).status == "warn"


def test_limits_can_differ_per_series(tmp_path):
    con, models = project(tmp_path, months([*CALM, 130]))  # +23.8%, over 3 times the usual move
    assert run(con, models).status == "pass"
    tighter = {**LIMITS, "stg_series.value": {"max_change_pct": 10}}
    result = run(con, models, limits=tighter)
    assert result.message.startswith("1 month moved more than 10%")


@pytest.mark.parametrize(
    "limits, message",
    [
        ({}, "anomaly limits must set"),
        ({"defaults": {"max_change_pct": 40}}, "anomaly limits must set"),
        (
            {"defaults": {**LIMITS["defaults"], "max_change": 40}},
            "anomaly limits must set",
        ),
        (
            {"defaults": {**LIMITS["defaults"], "max_change_pct": 0}},
            "max_change_pct must be a positive number",
        ),
        (
            {"defaults": {**LIMITS["defaults"], "typical_multiple": "3"}},
            "typical_multiple must be a positive number",
        ),
        (
            {"defaults": {**LIMITS["defaults"], "min_history_months": True}},
            "min_history_months must be a positive number",
        ),
        (
            {**LIMITS, "stg_series.valeu": {"max_change_pct": 5}},
            r"checks that do not exist: \['stg_series.valeu'\]",
        ),
    ],
)
def test_bad_limits_are_config_errors(tmp_path, limits, message):
    con, models = project(tmp_path, months(CALM))
    with pytest.raises(QualityConfigError, match=message):
        build_checks(schema(limits=limits), models, TODAY)


def _monthly_project(settings):
    models = settings.root / "models" / "staging"
    models.mkdir(parents=True)
    (models / "stg_trips.sql").write_text(
        "select month::date as month_start, total::int as total from {{ source('trips') }}",
        encoding="utf-8",
    )
    (settings.root / "config").mkdir()
    (settings.root / "config" / "quality.yml").write_text(
        "anomaly:\n  defaults: {max_change_pct: 40, typical_multiple: 3, min_history_months: 12}\n",
        encoding="utf-8",
    )
    raw = b"month,total\n2026-01-01,100\n2026-02-01,500\n"
    write_raw(settings, "trips", raw)


def test_a_jump_warns_but_does_not_stop_the_build(settings):
    _monthly_project(settings)
    (settings.root / "models" / "schema.yml").write_text(
        "models:\n"
        "  - name: stg_trips\n"
        "    columns:\n"
        "      - name: total\n"
        "        tests: [anomaly]\n",
        encoding="utf-8",
    )
    result = build_warehouse(settings, make_catalogue("trips"), run_tests=True, today=TODAY)
    assert [(r.kind, r.status) for r in result.checks] == [("anomaly", "warn")]

    con = connect(settings.warehouse_path, read_only=True)
    assert con.execute("select count(*) from staging.stg_trips").fetchone() == (2,)
    [(status, message)] = con.execute("select status, message from audit.check_results").fetchall()
    con.close()
    assert status == "warn"
    assert message.endswith("2026-02 +400.0%")


def test_severity_error_can_make_a_jump_stop_the_build(settings):
    _monthly_project(settings)
    (settings.root / "models" / "schema.yml").write_text(
        "models:\n"
        "  - name: stg_trips\n"
        "    columns:\n"
        "      - name: total\n"
        "        tests:\n"
        "          - anomaly: {severity: error}\n",
        encoding="utf-8",
    )
    with pytest.raises(DataQualityError, match="anomaly.stg_trips.total"):
        build_warehouse(settings, make_catalogue("trips"), run_tests=True, today=TODAY)


def project_anomaly_checks():
    models = discover(PROJECT_ROOT / "models")
    checks = build_checks(load_schema(PROJECT_ROOT / "models" / "schema.yml"), models, TODAY)
    return [c for c in checks if c.kind == "anomaly"]


def test_project_limits_come_from_the_config_folder():
    limits = load_schema(PROJECT_ROOT / "models" / "schema.yml")["limits"]["anomaly"]
    assert limits["defaults"]["max_change_pct"] == 40
    assert limits["fct_cpi_monthly.cpi_index"]["max_change_pct"] == 5


def test_schema_loads_without_a_limits_file(tmp_path):
    (tmp_path / "models").mkdir()
    path = tmp_path / "models" / "schema.yml"
    path.write_text("models: []\n", encoding="utf-8")
    assert load_schema(path) == {"models": []}


def test_project_checks_cover_the_monthly_series_and_their_queries_work(warehouse):
    checks = project_anomaly_checks()
    assert {c.name for c in checks} == {
        "anomaly.fct_cpi_monthly.cpi_index",
        "anomaly.fct_travel_monthly.airport_passengers",
        "anomaly.fct_travel_monthly.hotel_guests",
        "anomaly.fct_travel_monthly.hotel_nights",
    }
    # a warn-level check with a broken query would otherwise look like any other warning
    assert not [r.message for r in run_checks(warehouse, checks) if "query failed" in r.message]


def test_project_checks_are_warnings_only():
    assert {c.severity for c in project_anomaly_checks()} == {"warn"}


def test_real_jump_in_the_fixtures_matches_the_change_in_the_mart(warehouse):
    results = {r.name: r for r in run_checks(warehouse, project_anomaly_checks())}
    [(change,)] = warehouse.execute(
        "select mom_change_pct from marts.fct_cpi_monthly "
        "where group_short_name_en = 'Tobacco' and month_start = date '2020-02-01'"
    ).fetchall()
    assert f"Tobacco 2020-02 {change:+.1f}%" in results["anomaly.fct_cpi_monthly.cpi_index"].message
    assert change == pytest.approx(100 * (246 / 227 - 1))
