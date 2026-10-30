"""Load, transform and test steps wired together.

The build follows a write-audit-publish pattern: raw tables and models are
rebuilt inside one DuckDB transaction, the data tests run against that
uncommitted state, and the transaction is only committed when no error-level
test fails. A bad source file therefore never replaces the data the
dashboard is reading. Test results are recorded either way.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import duckdb

from pipeline.config import Catalogue, Settings
from pipeline.load import load_raw, load_seeds
from pipeline.quality import (
    CheckResult,
    DataQualityError,
    build_checks,
    load_schema,
    record_results,
    run_checks,
)
from pipeline.transform import ModelRun, discover, record_model_runs, run_models
from pipeline.warehouse import connect, transaction

log = logging.getLogger(__name__)


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


@dataclass
class BuildResult:
    run_id: str
    models: list[ModelRun] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)


def _checks_for(settings: Settings, today: date | None):
    models = discover(settings.models_dir)
    schema = load_schema(settings.schema_file)
    return build_checks(schema, models, today or date.today())


def build_warehouse(
    settings: Settings,
    catalogue: Catalogue,
    select: list[str] | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
    run_tests: bool = False,
    today: date | None = None,
) -> BuildResult:
    """Load raw files and seeds, run the models and optionally the data tests.

    Everything happens in one transaction; any failure (including an
    error-level data test) leaves the warehouse in its previous state.
    """
    models = discover(settings.models_dir)
    checks = _checks_for(settings, today) if run_tests else []
    result = BuildResult(run_id=new_run_id())
    owns_connection = con is None
    con = con or connect(settings.warehouse_path)
    quality_error: DataQualityError | None = None
    try:
        try:
            with transaction(con):
                load_seeds(con, settings.seeds_dir)
                load_raw(con, settings, catalogue)
                result.models = run_models(con, models, select)
                record_model_runs(con, result.run_id, result.models)
                if run_tests:
                    result.checks = run_checks(con, checks)
                    failed = [r for r in result.checks if r.failed]
                    if failed:
                        raise DataQualityError(failed, result.checks)
        except DataQualityError as exc:
            quality_error = exc
            log.error("data tests failed, build rolled back")
        if result.checks:
            with transaction(con):
                record_results(con, result.run_id, result.checks)
    finally:
        if owns_connection:
            con.close()
    if quality_error:
        raise quality_error
    log.info("built %d models (run %s)", len(result.models), result.run_id)
    return result


def check_warehouse(settings: Settings, today: date | None = None) -> BuildResult:
    """Run the data tests against the warehouse as it is now."""
    checks = _checks_for(settings, today)
    result = BuildResult(run_id=new_run_id())
    con = connect(settings.warehouse_path)
    try:
        result.checks = run_checks(con, checks)
        with transaction(con):
            record_results(con, result.run_id, result.checks)
    finally:
        con.close()
    failed = [r for r in result.checks if r.failed]
    if failed:
        raise DataQualityError(failed, result.checks)
    return result
