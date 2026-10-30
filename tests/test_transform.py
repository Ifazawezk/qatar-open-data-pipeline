from pathlib import Path

import pytest

from conftest import make_catalogue, write_raw
from pipeline.build import build_warehouse
from pipeline.transform import (
    ModelError,
    compile_sql,
    discover,
    execution_order,
    parse_model,
    run_models,
)
from pipeline.warehouse import connect


def add_model(root: Path, layer: str, name: str, sql: str) -> Path:
    path = root / "models" / layer / f"{name}.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")
    return path


def test_parse_model_reads_placeholders_and_description(tmp_path):
    path = add_model(
        tmp_path,
        "intermediate",
        "int_example",
        "-- Joins prices with months.\n"
        "-- Second line of the description.\n"
        "-- materialized: table\n"
        "select * from {{ ref('stg_a') }} join {{ seed('months') }} using (m)\n"
        "union all select * from {{ ref( \"stg_a\" ) }}, {{ source('cpi') }}\n",
    )
    model = parse_model(path, "intermediate")
    assert model.refs == ("stg_a",)
    assert model.seeds == ("months",)
    assert model.sources == ("cpi",)
    assert model.materialized == "table"
    assert model.description == "Joins prices with months. Second line of the description."


def test_unknown_placeholder_is_an_error(tmp_path):
    path = add_model(tmp_path, "staging", "stg_x", "select {{ var('x') }}")
    with pytest.raises(ModelError, match="cannot understand placeholder"):
        parse_model(path, "staging")


def test_compile_replaces_placeholders_with_relations(tmp_path):
    add_model(tmp_path, "staging", "stg_a", "select 1 as m from {{ source('cpi') }};")
    add_model(tmp_path, "marts", "fct_a", "select * from {{ ref('stg_a') }}")
    models = discover(tmp_path / "models")
    assert compile_sql(models["stg_a"], models) == "select 1 as m from raw.cpi"
    assert compile_sql(models["fct_a"], models) == "select * from staging.stg_a"


def test_order_follows_dependencies_across_layers(tmp_path):
    add_model(tmp_path, "staging", "stg_b", "select 2 as x")
    add_model(tmp_path, "staging", "stg_a", "select 1 as x")
    add_model(
        tmp_path, "intermediate", "int_ab", "select * from {{ ref('stg_a') }}, {{ ref('stg_b') }}"
    )
    add_model(tmp_path, "marts", "fct_ab", "select * from {{ ref('int_ab') }}")
    order = execution_order(discover(tmp_path / "models"))
    assert order.index("int_ab") > max(order.index("stg_a"), order.index("stg_b"))
    assert order[-1] == "fct_ab"


def test_unknown_reference_is_reported(tmp_path):
    add_model(tmp_path, "marts", "fct_a", "select * from {{ ref('stg_missing') }}")
    with pytest.raises(ModelError, match="unknown model 'stg_missing'"):
        execution_order(discover(tmp_path / "models"))


def test_cycles_are_reported(tmp_path):
    add_model(tmp_path, "intermediate", "int_a", "select * from {{ ref('int_b') }}")
    add_model(tmp_path, "intermediate", "int_b", "select * from {{ ref('int_a') }}")
    with pytest.raises(ModelError, match="dependency cycle"):
        execution_order(discover(tmp_path / "models"))


def test_staging_cannot_read_from_marts(tmp_path):
    add_model(tmp_path, "marts", "fct_a", "select 1 as x")
    add_model(tmp_path, "staging", "stg_a", "select * from {{ ref('fct_a') }}")
    with pytest.raises(ModelError, match=r"stg_a \(staging\) cannot depend on fct_a \(marts\)"):
        execution_order(discover(tmp_path / "models"))


def test_duplicate_model_names_are_rejected(tmp_path):
    add_model(tmp_path, "staging", "same", "select 1 as x")
    add_model(tmp_path, "marts", "same", "select 1 as x")
    with pytest.raises(ModelError, match="used twice"):
        discover(tmp_path / "models")


def test_run_models_creates_views_and_tables(tmp_path):
    add_model(tmp_path, "staging", "stg_a", "select range as x from range(5)")
    add_model(tmp_path, "marts", "fct_a", "select sum(x) as total from {{ ref('stg_a') }}")
    con = connect(":memory:")
    runs = run_models(con, discover(tmp_path / "models"))

    kinds = dict(
        con.execute(
            "select table_name, table_type from information_schema.tables "
            "where table_schema in ('staging', 'marts')"
        ).fetchall()
    )
    assert kinds == {"stg_a": "VIEW", "fct_a": "BASE TABLE"}
    assert con.execute("select total from marts.fct_a").fetchone() == (10,)
    assert [(r.name, r.rows) for r in runs] == [("stg_a", 5), ("fct_a", 1)]


def test_switching_materialization_replaces_the_old_object(tmp_path):
    path = add_model(tmp_path, "staging", "stg_a", "select 1 as x")
    con = connect(":memory:")
    run_models(con, discover(tmp_path / "models"))
    path.write_text("-- materialized: table\nselect 2 as x", encoding="utf-8")
    run_models(con, discover(tmp_path / "models"))
    assert con.execute("select x from staging.stg_a").fetchone() == (2,)


def test_select_runs_only_the_model_and_its_parents(tmp_path):
    add_model(tmp_path, "staging", "stg_a", "select 1 as x")
    add_model(tmp_path, "staging", "stg_b", "select 2 as x")
    add_model(tmp_path, "marts", "fct_a", "select * from {{ ref('stg_a') }}")
    runs = run_models(connect(":memory:"), discover(tmp_path / "models"), select=["fct_a"])
    assert [r.name for r in runs] == ["stg_a", "fct_a"]


def test_failed_build_leaves_the_warehouse_unchanged(settings):
    write_raw(settings, "trips", b"year,total\n2022,10\n")
    catalogue = make_catalogue("trips")
    add_model(
        settings.root, "staging", "stg_trips", "select year::int as year from {{ source('trips') }}"
    )
    build_warehouse(settings, catalogue)

    add_model(
        settings.root, "marts", "fct_broken", "select no_such_column from {{ ref('stg_trips') }}"
    )
    add_model(settings.root, "staging", "stg_trips", "select 1999 as year")
    with pytest.raises(ModelError, match="fct_broken"):
        build_warehouse(settings, catalogue)

    con = connect(settings.warehouse_path, read_only=True)
    assert con.execute("select year from staging.stg_trips").fetchone() == (2022,)
    assert con.execute(
        "select count(*) from information_schema.tables where table_name = 'fct_broken'"
    ).fetchone() == (0,)
    runs = con.execute("select count(distinct run_id) from audit.model_runs").fetchone()
    assert runs == (1,)
