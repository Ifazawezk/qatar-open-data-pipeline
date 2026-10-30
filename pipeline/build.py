"""Load and transform steps wired together."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import duckdb

from pipeline.config import Catalogue, Settings
from pipeline.load import load_raw, load_seeds
from pipeline.transform import ModelRun, discover, record_model_runs, run_models
from pipeline.warehouse import connect, transaction

log = logging.getLogger(__name__)


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


@dataclass
class BuildResult:
    run_id: str
    models: list[ModelRun] = field(default_factory=list)


def build_warehouse(
    settings: Settings,
    catalogue: Catalogue,
    select: list[str] | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
) -> BuildResult:
    """Load raw files and seeds, then run the models, all in one transaction.

    If anything fails the warehouse keeps its previous state.
    """
    models = discover(settings.models_dir)
    result = BuildResult(run_id=new_run_id())
    owns_connection = con is None
    con = con or connect(settings.warehouse_path)
    try:
        with transaction(con):
            load_seeds(con, settings.seeds_dir)
            load_raw(con, settings, catalogue)
            result.models = run_models(con, models, select)
            record_model_runs(con, result.run_id, result.models)
    finally:
        if owns_connection:
            con.close()
    log.info("built %d models (run %s)", len(result.models), result.run_id)
    return result
