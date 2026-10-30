"""Small task runner so the same commands work on Windows, macOS and Linux.

Usage: python tasks.py <task>    (python tasks.py help lists the tasks)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

TASKS: dict[str, tuple[str, list[list[str]]]] = {
    "setup": (
        "install runtime and dev dependencies",
        [[PY, "-m", "pip", "install", "-r", "requirements-dev.txt"]],
    ),
    "test": ("run the unit tests", [[PY, "-m", "pytest"]]),
    "lint": (
        "check style with ruff",
        [[PY, "-m", "ruff", "check", "."], [PY, "-m", "ruff", "format", "--check", "."]],
    ),
    "format": ("format the code with ruff", [[PY, "-m", "ruff", "format", "."]]),
    "sources": ("list configured datasets", [[PY, "-m", "pipeline", "sources"]]),
    "extract": ("download raw datasets from the portal", [[PY, "-m", "pipeline", "extract"]]),
}


def clean() -> None:
    for pattern in ("**/__pycache__", ".pytest_cache", ".ruff_cache"):
        for path in ROOT.glob(pattern):
            shutil.rmtree(path, ignore_errors=True)
    print("removed caches")


def usage() -> None:
    print(__doc__)
    width = max(len(name) for name in TASKS) + 2
    for name, (help_text, _) in TASKS.items():
        print(f"  {name:<{width}}{help_text}")
    print(f"  {'clean':<{width}}remove Python and tool caches")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"help", "-h", "--help"}:
        usage()
        return 0
    name = argv[0]
    if name == "clean":
        clean()
        return 0
    if name not in TASKS:
        print(f"unknown task '{name}'\n")
        usage()
        return 2
    for command in TASKS[name][1]:
        shown = " ".join(Path(part).name if part == PY else part for part in command)
        print("$", shown, flush=True)
        code = subprocess.call(command + argv[1:], cwd=ROOT)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
