"""Command line entry point: python -m pipeline <command>."""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import __version__
from pipeline.config import ConfigError, Settings, load_catalogue

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
