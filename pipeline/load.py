"""Load raw CSV files and seed files into DuckDB.

Raw tables keep every column as VARCHAR, exactly as the portal published it.
Typing and cleaning happen in the staging models, where they are visible and
tested, instead of being hidden in loader options.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline.config import Catalogue, Settings
from pipeline.extract import Manifest, sha256_file

log = logging.getLogger(__name__)

MANIFEST_TABLE = "audit.source_manifest"


class LoadError(RuntimeError):
    """Raw files are missing, changed since extract, or did not load cleanly."""


@dataclass
class LoadResult:
    relation: str
    rows: int


def _read_csv_as_text(con: duckdb.DuckDBPyConnection, relation: str, path: Path) -> int:
    con.execute(
        f"CREATE OR REPLACE TABLE {relation} AS "
        "SELECT * FROM read_csv(?, header = true, delim = ',', all_varchar = true)",
        [str(path)],
    )
    return con.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]


def load_raw(
    con: duckdb.DuckDBPyConnection, settings: Settings, catalogue: Catalogue
) -> list[LoadResult]:
    """Load every configured source into raw.<key> and record the manifest."""
    manifest = Manifest(settings.manifest_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS audit")

    results = []
    for source in catalogue.sources:
        entry = manifest.get(source.key)
        if entry is None:
            raise LoadError(f"{source.key}: not in the manifest, run `python -m pipeline extract`")
        path = settings.raw_dir / entry.file
        if not path.exists():
            raise LoadError(f"{source.key}: raw file {path} is missing")
        if sha256_file(path) != entry.sha256:
            raise LoadError(f"{source.key}: {path.name} changed since it was extracted")

        relation = f"raw.{source.key}"
        rows = _read_csv_as_text(con, relation, path)
        if rows != entry.row_count:
            raise LoadError(
                f"{relation}: loaded {rows} rows but the manifest says {entry.row_count}"
            )
        log.debug("loaded %s (%d rows)", relation, rows)
        results.append(LoadResult(relation, rows))

    con.execute(f"""
        CREATE OR REPLACE TABLE {MANIFEST_TABLE} (
            source_key VARCHAR PRIMARY KEY,
            dataset_id VARCHAR NOT NULL,
            title VARCHAR,
            publisher VARCHAR,
            source_url VARCHAR,
            page_url VARCHAR,
            licence VARCHAR,
            fetched_at TIMESTAMPTZ NOT NULL,
            checked_at TIMESTAMPTZ NOT NULL,
            source_modified TIMESTAMPTZ,
            row_count INTEGER NOT NULL,
            sha256 VARCHAR NOT NULL,
            bytes INTEGER
        )
    """)
    for key in catalogue.keys:
        e = manifest.get(key)
        con.execute(
            f"INSERT INTO {MANIFEST_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                e.key,
                e.dataset_id,
                e.title,
                e.publisher,
                e.source_url,
                e.page_url,
                e.licence,
                e.fetched_at,
                e.checked_at,
                e.source_modified,
                e.row_count,
                e.sha256,
                e.bytes,
            ],
        )
    log.info("loaded %d raw tables", len(results))
    return results


def load_seeds(con: duckdb.DuckDBPyConnection, seeds_dir: Path) -> list[LoadResult]:
    """Load small hand-maintained lookup tables from seeds/*.csv into seeds.<name>."""
    con.execute("CREATE SCHEMA IF NOT EXISTS seeds")
    results = []
    for path in sorted(seeds_dir.glob("*.csv")):
        relation = f"seeds.{path.stem}"
        results.append(LoadResult(relation, _read_csv_as_text(con, relation, path)))
    if results:
        log.info("loaded %d seed tables", len(results))
    return results
