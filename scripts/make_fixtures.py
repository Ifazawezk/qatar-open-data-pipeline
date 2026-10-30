"""Cut small test fixtures out of the real raw files in data/raw.

The fixtures keep the exact bytes of the selected lines (BOM, quoting, odd
spacing) so the tests exercise the same parsing problems as the real data.
Run it after `python -m pipeline extract`:

    python scripts/make_fixtures.py
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "tests" / "fixtures" / "raw"

Row = dict[str, str]

KEEP: dict[str, Callable[[Row], bool]] = {
    "population_labour_force": lambda r: r["year"] in {"2024", "2025"},
    "cpi_monthly": lambda r: (
        r["year"] in {"2020", "2021"} and r["group_code"] in {"0", "001", "002"}
    ),
    "hia_passengers": lambda r: r["year"] in {"2021", "2022"},
    "hotel_guests_nights": lambda r: r["year"][:4] in {"2021", "2022"},
    "electricity_by_zone": lambda r: (
        r["zone_number"] in {"1", "2", "69", "70"} and r["year"] in {"2024", "2025", "2026"}
    ),
    "water_by_zone": lambda r: (
        r["zone_number"] in {"1", "2", "69", "70"} and r["year"] in {"2024", "2025", "2026"}
    ),
    "zones": lambda r: r["number_of_zone"] in {"1", "2", "69", "70"},
}


def cut(key: str, keep: Callable[[Row], bool]) -> int:
    lines = (RAW / f"{key}.csv").read_bytes().decode("utf-8").splitlines(keepends=True)
    header = next(csv.reader([lines[0].lstrip("\ufeff")]))
    kept = [lines[0]]
    for line in lines[1:]:
        values = next(csv.reader([line]))
        if keep(dict(zip(header, values, strict=True))):
            kept.append(line)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}.csv").write_bytes("".join(kept).encode("utf-8"))
    return len(kept) - 1


if __name__ == "__main__":
    for key, keep in KEEP.items():
        print(f"{key:<26}{cut(key, keep):>5} rows")
