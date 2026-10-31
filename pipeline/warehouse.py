"""DuckDB connection helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb


def connect(path: Path | str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if str(path) != ":memory:" and not read_only:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


@contextmanager
def transaction(con: duckdb.DuckDBPyConnection) -> Iterator[duckdb.DuckDBPyConnection]:
    """Run a block in one transaction: commit on success, roll back on any error.

    DuckDB DDL is transactional, so a failed build leaves the previous tables
    and views exactly as they were.
    """
    con.execute("BEGIN TRANSACTION")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")


def relation_exists(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> str | None:
    """Return 'table', 'view' or None for schema.name."""
    row = con.execute(
        """
        SELECT CASE WHEN table_type = 'VIEW' THEN 'view' ELSE 'table' END
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, name],
    ).fetchone()
    return row[0] if row else None


def table_columns(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> list[tuple[str, str]]:
    """(column name, data type) pairs in table order; empty when the table does not exist."""
    return con.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position",
        [schema, name],
    ).fetchall()
