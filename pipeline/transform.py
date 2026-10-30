"""A small SQL model runner, similar in spirit to dbt.

Models are plain SELECT statements in models/<layer>/<name>.sql. They point
at other relations with three placeholders:

    {{ ref('stg_cpi_monthly') }}   another model   -> staging.stg_cpi_monthly
    {{ source('cpi_monthly') }}    a raw table     -> raw.cpi_monthly
    {{ source('audit', 'x') }}     another schema  -> audit.x
    {{ seed('months') }}           a lookup table  -> seeds.months

The runner reads the placeholders to work out dependencies, runs the models
in topological order and creates each one as a view or a table. Staging and
intermediate models are views by default, marts are tables. A model can
override that with a line `-- materialized: table` (or view).

Layers can only depend on the same or an earlier layer, so a staging model
can never quietly read from a mart.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

import duckdb

from pipeline.warehouse import relation_exists

log = logging.getLogger(__name__)

LAYERS = ("staging", "intermediate", "marts")
DEFAULT_MATERIALIZATION = {"staging": "view", "intermediate": "view", "marts": "table"}

_NAME = r"\s*['\"]([A-Za-z0-9_]+)['\"]\s*"
_REF = re.compile(r"\{\{\s*ref\(" + _NAME + r"\)\s*\}\}")
_SOURCE = re.compile(r"\{\{\s*source\(" + _NAME + r"(?:," + _NAME + r")?\)\s*\}\}")
_SEED = re.compile(r"\{\{\s*seed\(" + _NAME + r"\)\s*\}\}")
_ANY_PLACEHOLDER = re.compile(r"\{\{.*?\}\}", re.S)
_MATERIALIZED = re.compile(r"^--\s*materialized:\s*(\w+)\s*$", re.M | re.I)


class ModelError(ValueError):
    """The model files are inconsistent (bad reference, cycle, wrong layer...)."""


@dataclass(frozen=True)
class Model:
    name: str
    layer: str
    path: Path
    sql: str
    materialized: str
    refs: tuple[str, ...]
    sources: tuple[str, ...]
    seeds: tuple[str, ...]
    description: str

    @property
    def relation(self) -> str:
        return f"{self.layer}.{self.name}"


@dataclass
class ModelRun:
    name: str
    layer: str
    materialized: str
    rows: int
    seconds: float


def _source_relation(match: re.Match) -> str:
    """source('cpi') -> raw.cpi, source('audit', 'source_manifest') -> audit.source_manifest."""
    first, second = match.group(1), match.group(2)
    return f"{first}.{second}" if second else f"raw.{first}"


def _leading_comment(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped.startswith("--"):
            break
        if _MATERIALIZED.match(stripped):
            continue
        lines.append(stripped[2:].strip())
    return " ".join(part for part in lines if part)


def parse_model(path: Path, layer: str) -> Model:
    sql = path.read_text(encoding="utf-8")
    match = _MATERIALIZED.search(sql)
    materialized = match.group(1).lower() if match else DEFAULT_MATERIALIZATION[layer]
    if materialized not in {"view", "table"}:
        raise ModelError(f"{path.name}: unknown materialization '{materialized}'")

    known = _REF.sub("", _SOURCE.sub("", _SEED.sub("", sql)))
    leftover = _ANY_PLACEHOLDER.search(known)
    if leftover:
        raise ModelError(f"{path.name}: cannot understand placeholder {leftover.group(0)}")

    return Model(
        name=path.stem,
        layer=layer,
        path=path,
        sql=sql,
        materialized=materialized,
        refs=tuple(dict.fromkeys(_REF.findall(sql))),
        sources=tuple(dict.fromkeys(_source_relation(m) for m in _SOURCE.finditer(sql))),
        seeds=tuple(dict.fromkeys(_SEED.findall(sql))),
        description=_leading_comment(sql),
    )


def discover(models_dir: Path) -> dict[str, Model]:
    models: dict[str, Model] = {}
    for layer in LAYERS:
        for path in sorted((models_dir / layer).glob("*.sql")):
            model = parse_model(path, layer)
            if model.name in models:
                other = models[model.name].path
                raise ModelError(f"model name '{model.name}' is used twice: {other} and {path}")
            models[model.name] = model
    return models


def execution_order(models: dict[str, Model]) -> list[str]:
    graph: dict[str, set[str]] = {}
    for model in models.values():
        for ref in model.refs:
            if ref not in models:
                raise ModelError(f"{model.name} refers to unknown model '{ref}'")
            upstream = models[ref]
            if LAYERS.index(upstream.layer) > LAYERS.index(model.layer):
                raise ModelError(
                    f"{model.name} ({model.layer}) cannot depend on {ref} ({upstream.layer})"
                )
        graph[model.name] = set(model.refs)
    try:
        # sorted input keeps the order stable between runs
        return list(TopologicalSorter(dict(sorted(graph.items()))).static_order())
    except CycleError as exc:
        cycle = " -> ".join(exc.args[1])
        raise ModelError(f"dependency cycle: {cycle}") from exc


def upstream_of(models: dict[str, Model], names: list[str]) -> set[str]:
    """The given models plus everything they depend on."""
    wanted: set[str] = set()
    stack = list(names)
    while stack:
        name = stack.pop()
        if name not in models:
            raise ModelError(f"unknown model '{name}'")
        if name not in wanted:
            wanted.add(name)
            stack.extend(models[name].refs)
    return wanted


def compile_sql(model: Model, models: dict[str, Model]) -> str:
    sql = _REF.sub(lambda m: models[m.group(1)].relation, model.sql)
    sql = _SOURCE.sub(_source_relation, sql)
    sql = _SEED.sub(lambda m: f"seeds.{m.group(1)}", sql)
    return sql.strip().rstrip(";")


def run_models(
    con: duckdb.DuckDBPyConnection,
    models: dict[str, Model],
    select: list[str] | None = None,
) -> list[ModelRun]:
    """Create every model (or the selected ones and their parents) in order."""
    order = execution_order(models)
    if select:
        wanted = upstream_of(models, select)
        order = [name for name in order if name in wanted]

    for layer in LAYERS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {layer}")

    runs = []
    for name in order:
        model = models[name]
        started = time.perf_counter()
        existing = relation_exists(con, model.layer, model.name)
        if existing and existing != model.materialized:
            con.execute(f"DROP {existing.upper()} {model.relation}")
        kind = model.materialized.upper()
        try:
            con.execute(
                f"CREATE OR REPLACE {kind} {model.relation} AS\n{compile_sql(model, models)}"
            )
        except duckdb.Error as exc:
            raise ModelError(f"{model.relation} failed: {exc}") from exc
        rows = con.execute(f"SELECT count(*) FROM {model.relation}").fetchone()[0]
        seconds = time.perf_counter() - started
        log.info("%-40s %-5s %7d rows  %.2fs", model.relation, model.materialized, rows, seconds)
        runs.append(ModelRun(model.name, model.layer, model.materialized, rows, seconds))
    return runs


def record_model_runs(con: duckdb.DuckDBPyConnection, run_id: str, runs: list[ModelRun]) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS audit")
    con.execute("""
        CREATE TABLE IF NOT EXISTS audit.model_runs (
            run_id VARCHAR,
            finished_at TIMESTAMPTZ DEFAULT current_timestamp,
            model VARCHAR,
            layer VARCHAR,
            materialized VARCHAR,
            row_count BIGINT,
            seconds DOUBLE
        )
    """)
    for r in runs:
        con.execute(
            "INSERT INTO audit.model_runs (run_id, model, layer, materialized, row_count, seconds) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, r.name, r.layer, r.materialized, r.rows, r.seconds],
        )
