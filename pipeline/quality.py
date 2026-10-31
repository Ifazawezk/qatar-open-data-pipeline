"""Data quality checks declared in models/schema.yml.

Every check turns into one SQL query. Most count the rows that break a rule
(zero means pass); freshness checks look at the newest date instead.

Supported checks:

    column level   not_null, unique, accepted_values, range, relationships, anomaly
    model level    unique (several columns), row_count, expression, query, freshness
    sources        freshness of the raw files (from the extract manifest)

Each check can set `severity: warn`. Warnings are printed but do not fail the
run; anything at the default `error` severity does. Anomaly checks default to
`warn`, because a sudden jump can be a real event. Their limits are in
config/quality.yml.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from pipeline.transform import Model, compile_sql

log = logging.getLogger(__name__)

SEVERITIES = ("error", "warn")
ANOMALY_LIMITS = ("max_change_pct", "min_history_months", "typical_multiple")


class QualityConfigError(ValueError):
    """schema.yml refers to unknown models/columns or uses an unknown check."""


class DataQualityError(RuntimeError):
    """At least one error-level check failed."""

    def __init__(self, failed: list[CheckResult], results: list[CheckResult] | None = None):
        self.failed = failed
        self.results = results or failed
        names = ", ".join(r.name for r in failed[:5])
        more = f" and {len(failed) - 5} more" if len(failed) > 5 else ""
        super().__init__(f"{len(failed)} data quality check(s) failed: {names}{more}")


@dataclass(frozen=True)
class Check:
    name: str
    model: str
    kind: str
    severity: str
    sql: str
    evaluate: Callable[[Any], tuple[bool, str]] = field(compare=False, repr=False)
    column: str | None = None


@dataclass
class CheckResult:
    name: str
    model: str
    kind: str
    severity: str
    status: str  # pass | warn | fail
    message: str
    column: str | None = None

    @property
    def failed(self) -> bool:
        return self.status == "fail"


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _count_is_zero(what: str) -> Callable[[Any], tuple[bool, str]]:
    def evaluate(count: Any) -> tuple[bool, str]:
        count = int(count or 0)
        return count == 0, f"{count} {what}" if count else "ok"

    return evaluate


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _freshness(
    label: str, today: date, warn_after: int | None, error_after: int | None
) -> Callable[[Any], tuple[bool, str]]:
    """Returns (ok, message); a 'warn' outcome is signalled with ok=None."""

    def evaluate(value: Any) -> tuple[bool | None, str]:
        newest = _to_date(value)
        if newest is None:
            return False, f"no {label} found"
        age = (today - newest).days
        message = f"latest {label} is {newest} ({age} days old)"
        if error_after is not None and age > error_after:
            return False, f"{message}, limit is {error_after}"
        if warn_after is not None and age > warn_after:
            return None, f"{message}, warn after {warn_after}"
        return True, message

    return evaluate


def _no_jumps(limit: float) -> Callable[[Any], tuple[bool, str]]:
    def evaluate(jumps: Any) -> tuple[bool, str]:
        if not jumps:
            return True, f"no month moved more than {limit}%"
        listed = ", ".join(
            " ".join(filter(None, [j["series"], j["month"], f"{j['change_pct']:+.1f}%"]))
            for j in jumps
        )
        months = "1 month" if len(jumps) == 1 else f"{len(jumps)} months"
        return False, f"{months} moved more than {limit}% on the previous month: {listed}"

    return evaluate


def _anomaly_sql(
    relation: str, column: str, time_column: str, by: str | None, limits: dict[str, float]
) -> str:
    """One value: a list of the flagged months, or NULL when there are none.

    Each month is joined to the calendar month before it, never to the row
    before it, so a gap in the data gives no comparison instead of a wrong one.
    A previous value of zero has no percentage change and is skipped.
    """
    series = by or "cast(null as varchar)"
    return f"""
        with points as (
            select {time_column} as month, {series} as series, {column} as value
            from {relation}
            where {column} is not null
        ),
        changes as (
            select
                cur.month,
                cur.series,
                100.0 * (cur.value / prev.value - 1) as change_pct
            from points as cur
            join points as prev
                on prev.month = cur.month - interval 1 month
                and prev.series is not distinct from cur.series
            where prev.value > 0
        ),
        usual as (
            select series, median(abs(change_pct)) as typical, count(*) as months
            from changes
            group by series
        )
        select list(
            {{
                'month': strftime(changes.month, '%Y-%m'),
                'series': changes.series,
                'change_pct': changes.change_pct
            }}
            order by changes.month, changes.series
        )
        from changes
        join usual on usual.series is not distinct from changes.series
        where abs(changes.change_pct) > {_literal(limits["max_change_pct"])}
            and (
                usual.months < {_literal(limits["min_history_months"])}
                or abs(changes.change_pct) > {_literal(limits["typical_multiple"])} * usual.typical
            )
    """


class _Builder:
    """Turns the YAML entries for one model into Check objects."""

    def __init__(
        self,
        model: Model,
        models: dict[str, Model],
        today: date,
        anomaly_limits: dict | None = None,
    ):
        self.model = model
        self.models = models
        self.today = today
        self.anomaly_limits = anomaly_limits or {}
        self.rel = model.relation
        self.checks: list[Check] = []

    def add(self, kind, sql, evaluate, severity="error", column=None, suffix=None):
        if severity not in SEVERITIES:
            raise QualityConfigError(f"{self.model.name}: unknown severity '{severity}'")
        target = suffix or column or "table"
        name = f"{kind}.{self.model.name}.{target}"
        self.checks.append(Check(name, self.model.name, kind, severity, sql, evaluate, column))

    def column_check(self, column: str, spec: Any) -> None:
        kind, args = _split(spec)
        severity = args.pop("severity", "warn" if kind == "anomaly" else "error")
        rel = self.rel
        if kind == "not_null":
            sql = f"select count(*) from {rel} where {column} is null"
            self.add(kind, sql, _count_is_zero("null values"), severity, column)
        elif kind == "unique":
            sql = (
                f"select count(*) from (select {column} from {rel} where {column} is not null "
                f"group by {column} having count(*) > 1)"
            )
            self.add(kind, sql, _count_is_zero("duplicated values"), severity, column)
        elif kind == "accepted_values":
            values = ", ".join(_literal(v) for v in args["values"])
            sql = f"select count(*) from {rel} where {column} not in ({values})"
            self.add(kind, sql, _count_is_zero("rows with unexpected values"), severity, column)
        elif kind == "range":
            bounds = []
            if "min" in args:
                bounds.append(f"{column} < {_literal(args['min'])}")
            if "max" in args:
                bounds.append(f"{column} > {_literal(args['max'])}")
            if not bounds:
                raise QualityConfigError(f"{self.model.name}.{column}: range needs min or max")
            sql = f"select count(*) from {rel} where {' or '.join(bounds)}"
            limits = f"[{args.get('min', '-inf')}, {args.get('max', 'inf')}]"
            self.add(kind, sql, _count_is_zero(f"rows outside {limits}"), severity, column)
        elif kind == "relationships":
            parent = self._relation(args["to"])
            parent_field = args["field"]
            sql = (
                f"select count(*) from {rel} as child left join {parent} as parent "
                f"on child.{column} = parent.{parent_field} "
                f"where child.{column} is not null and parent.{parent_field} is null"
            )
            what = f"rows without a match in {args['to']}.{parent_field}"
            self.add(kind, sql, _count_is_zero(what), severity, column)
        elif kind == "anomaly":
            limits = self._limits_for(column)
            time_column = args.get("time_column", "month_start")
            sql = _anomaly_sql(rel, column, time_column, args.get("by"), limits)
            self.add(kind, sql, _no_jumps(limits["max_change_pct"]), severity, column)
        else:
            raise QualityConfigError(f"{self.model.name}.{column}: unknown check '{kind}'")

    def model_check(self, spec: Any) -> None:
        kind, args = _split(spec)
        if isinstance(args, list):  # unique: [a, b]
            args = {"columns": args}
        severity = args.pop("severity", "error")
        rel = self.rel
        if kind == "unique":
            cols = ", ".join(args["columns"])
            sql = (
                f"select count(*) from (select {cols} from {rel} "
                f"group by {cols} having count(*) > 1)"
            )
            suffix = "+".join(args["columns"])
            self.add(kind, sql, _count_is_zero("duplicated keys"), severity, suffix=suffix)
        elif kind == "row_count":
            low, high = args.get("min", 0), args.get("max")

            def evaluate(count, low=low, high=high):
                ok = count >= low and (high is None or count <= high)
                return ok, f"{count} rows (expected {low} to {high or 'any'})"

            self.add(kind, f"select count(*) from {rel}", evaluate, severity)
        elif kind == "expression":
            expr = args["sql"]
            sql = f"select count(*) from {rel} where not ({expr})"
            self.add(
                kind,
                sql,
                _count_is_zero(f"rows where not ({expr})"),
                severity,
                suffix=args.get("name", "expression"),
            )
        elif kind == "query":
            inner = self._compile(args["sql"])
            sql = f"select count(*) from ({inner})"
            self.add(kind, sql, _count_is_zero("rows returned"), severity, suffix=args["name"])
        elif kind == "freshness":
            column = args["column"]
            evaluate = _freshness(
                column, self.today, args.get("warn_after_days"), args.get("error_after_days")
            )
            self.add(kind, f"select max({column}) from {rel}", evaluate, severity, column)
        else:
            raise QualityConfigError(f"{self.model.name}: unknown check '{kind}'")

    def _limits_for(self, column: str) -> dict[str, float]:
        key = f"{self.model.name}.{column}"
        limits = {**self.anomaly_limits.get("defaults", {}), **self.anomaly_limits.get(key, {})}
        if sorted(limits) != sorted(ANOMALY_LIMITS):
            raise QualityConfigError(
                f"{key}: anomaly limits must set {', '.join(ANOMALY_LIMITS)}, got {sorted(limits)}"
            )
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
                raise QualityConfigError(f"{key}: {name} must be a positive number, got {value!r}")
        return limits

    def _relation(self, name: str) -> str:
        if name not in self.models:
            raise QualityConfigError(f"{self.model.name}: relationships to unknown model '{name}'")
        return self.models[name].relation

    def _compile(self, sql: str) -> str:
        fake = Model(
            name=self.model.name,
            layer=self.model.layer,
            path=self.model.path,
            sql=sql,
            materialized="view",
            refs=(),
            sources=(),
            seeds=(),
            description="",
        )
        return compile_sql(fake, self.models)


def _split(spec: Any) -> tuple[str, Any]:
    """'not_null' -> ('not_null', {}); {'range': {...}} -> ('range', {...})."""
    if isinstance(spec, str):
        return spec, {}
    if isinstance(spec, dict) and len(spec) == 1:
        kind, args = next(iter(spec.items()))
        return kind, (dict(args) if isinstance(args, dict) else args)
    raise QualityConfigError(f"cannot read check definition: {spec!r}")


def load_schema(path: Path) -> dict:
    """Read models/schema.yml and add the limits from config/quality.yml, if it exists."""
    with path.open(encoding="utf-8") as fh:
        schema = yaml.safe_load(fh) or {}
    limits_file = path.parent.parent / "config" / "quality.yml"
    if limits_file.exists():
        with limits_file.open(encoding="utf-8") as fh:
            schema["limits"] = yaml.safe_load(fh) or {}
    return schema


def build_checks(schema: dict, models: dict[str, Model], today: date) -> list[Check]:
    checks: list[Check] = []
    anomaly_limits = (schema.get("limits") or {}).get("anomaly") or {}
    for entry in schema.get("models", []):
        name = entry["name"]
        if name not in models:
            raise QualityConfigError(f"schema.yml describes unknown model '{name}'")
        builder = _Builder(models[name], models, today, anomaly_limits)
        for spec in entry.get("tests", []):
            builder.model_check(spec)
        for column in entry.get("columns", []):
            for spec in column.get("tests", []):
                builder.column_check(column["name"], spec)
        checks.extend(builder.checks)

    declared = {f"{c.model}.{c.column}" for c in checks if c.kind == "anomaly"}
    unused = sorted(set(anomaly_limits) - declared - {"defaults"})
    if unused:
        raise QualityConfigError(f"anomaly limits for checks that do not exist: {unused}")

    source_rules = (schema.get("sources") or {}).get("freshness")
    if source_rules:
        evaluate = _freshness(
            "check against the portal",
            today,
            source_rules.get("warn_after_days"),
            source_rules.get("error_after_days"),
        )
        checks.append(
            Check(
                name="freshness.sources.checked_at",
                model="sources",
                kind="freshness",
                severity="error",
                sql="select min(checked_at) from audit.source_manifest",
                evaluate=evaluate,
                column="checked_at",
            )
        )
    return checks


def run_checks(con: duckdb.DuckDBPyConnection, checks: list[Check]) -> list[CheckResult]:
    results = []
    for check in checks:
        try:
            value = con.execute(check.sql).fetchone()[0]
            ok, message = check.evaluate(value)
        except duckdb.Error as exc:
            ok, message = False, f"query failed: {exc}"
        if ok:
            status = "pass"
        elif ok is None or check.severity == "warn":
            status = "warn"
        else:
            status = "fail"
        results.append(
            CheckResult(
                check.name, check.model, check.kind, check.severity, status, message, check.column
            )
        )
    return results


def record_results(con: duckdb.DuckDBPyConnection, run_id: str, results: list[CheckResult]) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS audit")
    con.execute("""
        CREATE TABLE IF NOT EXISTS audit.check_results (
            run_id VARCHAR,
            checked_at TIMESTAMPTZ DEFAULT current_timestamp,
            check_name VARCHAR,
            model VARCHAR,
            column_name VARCHAR,
            kind VARCHAR,
            severity VARCHAR,
            status VARCHAR,
            message VARCHAR
        )
    """)
    for r in results:
        con.execute(
            "INSERT INTO audit.check_results "
            "(run_id, check_name, model, column_name, kind, severity, status, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [run_id, r.name, r.model, r.column, r.kind, r.severity, r.status, r.message],
        )


def summarise(results: list[CheckResult]) -> str:
    counts = {s: sum(r.status == s for r in results) for s in ("pass", "warn", "fail")}
    lines = []
    for r in results:
        if r.status != "pass":
            lines.append(f"  {r.status.upper():<5} {r.name}: {r.message}")
    lines.append(
        f"{len(results)} checks: {counts['pass']} passed, "
        f"{counts['warn']} warnings, {counts['fail']} failed"
    )
    return "\n".join(lines)
