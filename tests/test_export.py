"""The export command, checked against a warehouse built from the fixtures."""

import csv
import re

import pytest

from pipeline.cli import main
from pipeline.config import PROJECT_ROOT, Settings
from pipeline.export import BOM, ExportError, export_marts
from pipeline.transform import discover
from pipeline.warehouse import connect

MARTS = sorted(m.name for m in discover(PROJECT_ROOT / "models").values() if m.layer == "marts")


@pytest.fixture(scope="module")
def exported(fixture_settings, warehouse, tmp_path_factory):
    """Export once; every test below only reads the files."""
    out = tmp_path_factory.mktemp("exports")
    return out, export_marts(fixture_settings, out)


def parquet_columns(con, path):
    return dict(
        con.execute(
            "select column_name, column_type from "
            f"(describe select * from read_parquet('{path.as_posix()}'))"
        ).fetchall()
    )


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_every_mart_is_written_in_both_formats(exported):
    out, results = exported
    assert [r.name for r in results] == MARTS
    names = {p.name for p in out.iterdir()}
    assert names == {f"{m}.parquet" for m in MARTS} | {f"{m}.csv" for m in MARTS}


@pytest.mark.parametrize("mart", MARTS)
def test_parquet_has_the_same_rows_as_the_warehouse(exported, warehouse, mart):
    out, results = exported
    path = (out / f"{mart}.parquet").as_posix()
    source = f"(select * from marts.{mart})"
    copy = f"read_parquet('{path}')"
    [(only_in_source,)] = warehouse.execute(
        f"select count(*) from (from {source} except all from {copy})"
    ).fetchall()
    [(only_in_copy,)] = warehouse.execute(
        f"select count(*) from (from {copy} except all from {source})"
    ).fetchall()
    assert (only_in_source, only_in_copy) == (0, 0)
    assert (
        next(r.rows for r in results if r.name == mart)
        == warehouse.execute(f"select count(*) from marts.{mart}").fetchone()[0]
    )


def test_parquet_keeps_counts_as_integers_and_dates_as_dates(exported, warehouse):
    out, _ = exported
    travel = parquet_columns(warehouse, out / "fct_travel_monthly.parquet")
    assert travel["airport_passengers"] == "BIGINT"  # HUGEINT in the warehouse
    assert travel["hotel_guests"] == "BIGINT"
    assert travel["month_start"] == "DATE"
    assert travel["nights_per_guest"] == "DOUBLE"
    assert parquet_columns(warehouse, out / "dim_zone.parquet")["has_name"] == "BOOLEAN"


def test_parquet_has_no_type_power_bi_may_not_read(exported, warehouse):
    out, _ = exported
    seen = set()
    for mart in MARTS:
        seen |= set(parquet_columns(warehouse, out / f"{mart}.parquet").values())
    assert seen <= {"BIGINT", "BOOLEAN", "DATE", "DOUBLE", "INTEGER", "VARCHAR"}


def test_parquet_uses_snappy_and_format_version_1(exported, warehouse):
    out, _ = exported
    path = (out / "fct_cpi_monthly.parquet").as_posix()
    assert warehouse.execute(
        f"select distinct compression from parquet_metadata('{path}')"
    ).fetchall() == [("SNAPPY",)]
    assert warehouse.execute(
        f"select format_version from parquet_file_metadata('{path}')"
    ).fetchall() == [(1,)]


@pytest.mark.parametrize("mart", MARTS)
def test_csv_starts_with_a_bom_and_has_every_row(exported, warehouse, mart):
    out, _ = exported
    path = out / f"{mart}.csv"
    assert path.read_bytes().startswith(BOM)
    assert not path.read_bytes().startswith(BOM + BOM)
    rows = read_csv(path)
    [(expected,)] = warehouse.execute(f"select count(*) from marts.{mart}").fetchall()
    assert len(rows) == expected
    columns = [c[0] for c in warehouse.execute(f"describe marts.{mart}").fetchall()]
    assert list(rows[0]) == columns


def test_csv_keeps_arabic_labels(exported, warehouse):
    out, _ = exported
    rows = read_csv(out / "fct_cpi_monthly.csv")
    names = {r["group_code"]: r["group_name_ar"] for r in rows}
    [(expected,)] = warehouse.execute(
        "select distinct group_name_ar from marts.fct_cpi_monthly where group_code = '000'"
    ).fetchall()
    assert names["000"] == expected
    assert re.search(r"[؀-ۿ]", expected)


def test_csv_writes_whole_numbers_and_empty_cells_for_missing_values(exported):
    out, _ = exported
    rows = {r["month_start"]: r for r in read_csv(out / "fct_travel_monthly.csv")}
    row = rows["2022-12-01"]
    assert row["airport_passengers"] == str(1704952 + 1916866)  # not 3621818.0
    assert row["airport_passengers_yoy_pct"] != ""
    assert rows["2021-01-01"]["airport_passengers_yoy_pct"] == ""


def test_export_is_repeatable(fixture_settings, exported, tmp_path):
    out, _ = exported
    export_marts(fixture_settings, tmp_path)
    for path in out.iterdir():
        assert (tmp_path / path.name).read_bytes() == path.read_bytes()


def test_default_folder_is_exports_in_the_project_root(settings):
    assert settings.exports_dir == settings.root / "exports"


def test_missing_warehouse_is_a_clear_error(settings):
    with pytest.raises(ExportError, match="run `python -m pipeline run` first"):
        export_marts(settings)
    assert not settings.exports_dir.exists()


def test_missing_mart_stops_the_export_and_keeps_old_files(tmp_path):
    settings = Settings(
        root=PROJECT_ROOT, data_dir=tmp_path, warehouse_path=tmp_path / "partial.duckdb"
    )
    con = connect(settings.warehouse_path)
    con.execute("create schema marts")
    con.execute("create table marts.dim_month as select 1 as month")
    con.close()
    out = tmp_path / "exports"
    out.mkdir()
    (out / "dim_month.csv").write_text("previous export", encoding="utf-8")

    with pytest.raises(ExportError, match=r"marts\.dim_zone is missing"):
        export_marts(settings, out)

    assert [p.name for p in out.iterdir()] == ["dim_month.csv"]
    assert (out / "dim_month.csv").read_text(encoding="utf-8") == "previous export"


def test_file_open_in_another_program_gives_a_clear_error(
    fixture_settings, warehouse, tmp_path, monkeypatch
):
    def locked(source, target):
        raise PermissionError(13, "file is in use")

    monkeypatch.setattr("pipeline.export.os.replace", locked)
    with pytest.raises(ExportError, match="close it in Excel or Power BI"):
        export_marts(fixture_settings, tmp_path)
    assert list(tmp_path.iterdir()) == []  # the temporary folder is gone


def test_unwritable_folder_is_a_clear_error(fixture_settings, warehouse, tmp_path):
    blocked = tmp_path / "a_file"
    blocked.write_text("not a folder", encoding="utf-8")
    with pytest.raises(ExportError, match="cannot write to"):
        export_marts(fixture_settings, blocked)


def test_cli_exports_to_the_folder_it_is_given(fixture_settings, warehouse, tmp_path, monkeypatch):
    monkeypatch.setenv("QODP_WAREHOUSE", str(fixture_settings.warehouse_path))
    out = tmp_path / "out"
    assert main(["export", "--out", str(out)]) == 0
    assert (out / "dim_zone.parquet").exists()
    assert (out / "dim_zone.csv").exists()


def test_cli_exits_with_1_without_a_warehouse(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("QODP_WAREHOUSE", str(tmp_path / "nothing.duckdb"))
    assert main(["export", "--out", str(tmp_path / "out")]) == 1


def test_power_bi_guide_only_names_columns_that_exist(warehouse):
    """The DAX cannot be run here, so at least catch a mistyped table or column."""
    guide = (PROJECT_ROOT / "docs" / "power-bi.md").read_text(encoding="utf-8")
    named = set(re.findall(r"\b([a-z][a-z_]*)\[([a-z0-9_]+)\]", guide))
    assert ("fct_cpi_monthly", "is_general_index") in named
    known = set(
        warehouse.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = 'marts'"
        ).fetchall()
    )
    assert named - {("dim_year", "year")} <= known
