"""Write the marts to Parquet and CSV for Power BI, Excel and similar tools.

    python -m pipeline export

One Parquet file and one CSV file per mart, named after the mart. DuckDB
writes both formats, so this needs no extra packages and no network.

Parquet keeps the column types. DuckDB stores its HUGEINT totals as DOUBLE in
Parquet, so they are cast to BIGINT first and counts stay whole numbers.

The CSV files start with a UTF-8 byte order mark. Without it Excel reads them
in the local code page and the Arabic labels turn into gibberish.

Files go to a temporary folder first and are moved into place once every mart
has been written, so a failed query leaves the previous export as it was.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline.config import Settings
from pipeline.transform import Model, discover
from pipeline.warehouse import connect, table_columns

log = logging.getLogger(__name__)

BOM = b"\xef\xbb\xbf"


class ExportError(RuntimeError):
    """The marts could not be read or the files could not be written."""


@dataclass
class ExportedMart:
    name: str
    rows: int
    parquet: Path
    csv: Path


def _path_literal(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _select(con: duckdb.DuckDBPyConnection, model: Model) -> str:
    """Every column of a mart in a stable row order, with HUGEINT cast to BIGINT."""
    columns = table_columns(con, model.layer, model.name)
    if not columns:
        raise ExportError(f"{model.relation} is missing, run `python -m pipeline run` first")
    items = [
        f'cast("{name}" as bigint) as "{name}"' if data_type == "HUGEINT" else f'"{name}"'
        for name, data_type in columns
    ]
    return f"select {', '.join(items)} from {model.relation} order by all"


def _write_mart(con: duckdb.DuckDBPyConnection, model: Model, folder: Path) -> int:
    select = _select(con, model)
    parquet = folder / f"{model.name}.parquet"
    csv = folder / f"{model.name}.csv"
    con.execute(f"copy ({select}) to {_path_literal(parquet)} (format parquet, compression snappy)")
    con.execute(f"copy ({select}) to {_path_literal(csv)} (format csv, header true)")
    csv.write_bytes(BOM + csv.read_bytes())
    return con.execute(f"select count(*) from {model.relation}").fetchone()[0]


def _publish(folder: Path, out: Path) -> None:
    for path in sorted(folder.iterdir()):
        target = out / path.name
        try:
            os.replace(path, target)
        except PermissionError as exc:
            raise ExportError(
                f"cannot replace {target}, close it in Excel or Power BI and run the export again"
            ) from exc


def export_marts(settings: Settings, out: Path | None = None) -> list[ExportedMart]:
    """Write every mart to `out` (default exports/) and return what was written."""
    if not settings.warehouse_path.exists():
        raise ExportError("no warehouse yet, run `python -m pipeline run` first")
    out = out or settings.exports_dir
    marts = sorted(
        (m for m in discover(settings.models_dir).values() if m.layer == "marts"),
        key=lambda m: m.name,
    )
    try:
        out.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix=".export-", dir=out))
    except OSError as exc:
        raise ExportError(f"cannot write to {out}: {exc}") from exc

    try:
        con = connect(settings.warehouse_path, read_only=True)
        try:
            rows = {model.name: _write_mart(con, model, folder) for model in marts}
        finally:
            con.close()
        _publish(folder, out)
    except duckdb.Error as exc:
        raise ExportError(f"could not export the marts: {exc}") from exc
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    log.info("exported %d marts to %s", len(marts), out)
    return [
        ExportedMart(m.name, rows[m.name], out / f"{m.name}.parquet", out / f"{m.name}.csv")
        for m in marts
    ]
