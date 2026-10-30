import pytest

from conftest import make_catalogue, write_raw
from pipeline.load import LoadError, load_raw, load_seeds
from pipeline.warehouse import connect

ARABIC_CSV = '\ufeffyear,month,lshhr,total\n2022,January,يناير,10\n2022,February,فبراير,"1,5"\n'


def test_raw_tables_keep_text_and_arabic_labels(settings):
    write_raw(settings, "trips", ARABIC_CSV.encode())
    con = connect(":memory:")
    [result] = load_raw(con, settings, make_catalogue("trips"))

    assert result.rows == 2
    columns = con.execute("DESCRIBE raw.trips").fetchall()
    assert [c[0] for c in columns] == ["year", "month", "lshhr", "total"]
    assert {c[1] for c in columns} == {"VARCHAR"}
    assert con.execute("SELECT lshhr, total FROM raw.trips ORDER BY month").fetchall() == [
        ("فبراير", "1,5"),
        ("يناير", "10"),
    ]


def test_manifest_is_loaded_for_freshness_checks(settings):
    write_raw(settings, "trips", ARABIC_CSV.encode(), fetched_at="2026-10-01T06:00:00+00:00")
    con = connect(":memory:")
    load_raw(con, settings, make_catalogue("trips"))
    row = con.execute(
        "SELECT source_key, row_count, fetched_at::DATE::VARCHAR FROM audit.source_manifest"
    ).fetchone()
    assert row == ("trips", 2, "2026-10-01")


def test_missing_extract_is_reported(settings):
    with pytest.raises(LoadError, match="run `python -m pipeline extract`"):
        load_raw(connect(":memory:"), settings, make_catalogue("trips"))


def test_edited_raw_file_is_refused(settings):
    write_raw(settings, "trips", ARABIC_CSV.encode())
    (settings.raw_dir / "trips.csv").write_text("year\n2022\n", encoding="utf-8")
    with pytest.raises(LoadError, match="changed since it was extracted"):
        load_raw(connect(":memory:"), settings, make_catalogue("trips"))


def test_seeds_are_loaded_as_text(tmp_path):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "codes.csv").write_text("code,label\n001,Food\n", encoding="utf-8")
    con = connect(":memory:")
    [result] = load_seeds(con, seeds)
    assert result.relation == "seeds.codes"
    assert con.execute("SELECT code FROM seeds.codes").fetchone() == ("001",)
