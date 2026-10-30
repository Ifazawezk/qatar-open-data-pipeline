"""Command line entry point: python -m pipeline <command>."""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import __version__
from pipeline.build import build_warehouse
from pipeline.config import ConfigError, Settings, load_catalogue
from pipeline.extract import ExtractError, extract_all
from pipeline.load import LoadError
from pipeline.transform import ModelError

log = logging.getLogger("pipeline")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_sources(args: argparse.Namespace, settings: Settings) -> int:
    catalogue = load_catalogue(settings.sources_file)
    for source in catalogue.sources:
        print(f"{source.key:<26} {source.publisher:<28} {source.dataset_id}")
    return 0


def cmd_extract(args: argparse.Namespace, settings: Settings) -> int:
    catalogue = load_catalogue(settings.sources_file)
    results = extract_all(settings, catalogue, keys=args.only, force=args.force)
    print()
    print(f"{'source':<26}{'status':<12}{'rows':>8}{'bytes':>10}  fetched_at")
    for r in results:
        print(f"{r.key:<26}{r.status:<12}{r.row_count:>8}{r.bytes:>10}  {r.fetched_at}")
    return 0


def cmd_transform(args: argparse.Namespace, settings: Settings) -> int:
    catalogue = load_catalogue(settings.sources_file)
    result = build_warehouse(settings, catalogue, select=args.select)
    print(f"built {len(result.models)} models into {settings.warehouse_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description="Qatar open data pipeline (data.gov.qa -> DuckDB).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sources", help="list the configured datasets")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("extract", help="download raw datasets into data/raw")
    p.add_argument("--only", nargs="+", metavar="KEY", help="extract only these sources")
    p.add_argument("--force", action="store_true", help="ignore the cache and download again")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("transform", help="load raw files and build the SQL models")
    p.add_argument("--select", nargs="+", metavar="MODEL", help="build these models and parents")
    p.set_defaults(func=cmd_transform)
    return parser


def main(argv: list[str] | None = None) -> int:
    # The Windows console defaults to a legacy code page; Arabic labels need UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    settings = Settings.from_env()
    try:
        return args.func(args, settings)
    except ConfigError as exc:
        log.error("configuration problem: %s", exc)
        return 2
    except ExtractError as exc:
        log.error("extract failed: %s", exc)
        return 1
    except (LoadError, ModelError) as exc:
        log.error("transform failed, warehouse left unchanged: %s", exc)
        return 1
