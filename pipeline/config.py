"""Project paths and the source catalogue from config/sources.yml."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ConfigError(ValueError):
    """Raised when config/sources.yml is missing fields or inconsistent."""


@dataclass(frozen=True)
class PortalConfig:
    api_url: str
    site_url: str
    licence: str
    licence_url: str
    request_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    max_retries: int = 4
    backoff_seconds: float = 2.0
    cache_ttl_hours: float = 24.0
    user_agent: str = "qatar-open-data-pipeline/0.1"


@dataclass(frozen=True)
class Source:
    key: str
    dataset_id: str
    title: str
    publisher: str
    description: str = ""
    expected_columns: tuple[str, ...] = ()
    min_rows: int = 1

    def export_url(self, portal: PortalConfig) -> str:
        return f"{portal.api_url}/catalog/datasets/{self.dataset_id}/exports/csv"

    def metadata_url(self, portal: PortalConfig) -> str:
        return f"{portal.api_url}/catalog/datasets/{self.dataset_id}"

    def page_url(self, portal: PortalConfig) -> str:
        return f"{portal.site_url}/explore/dataset/{self.dataset_id}/"


@dataclass(frozen=True)
class Catalogue:
    portal: PortalConfig
    sources: tuple[Source, ...] = field(default_factory=tuple)

    def get(self, key: str) -> Source:
        for source in self.sources:
            if source.key == key:
                return source
        known = ", ".join(s.key for s in self.sources)
        raise ConfigError(f"unknown source '{key}'. Known sources: {known}")

    @property
    def keys(self) -> list[str]:
        return [s.key for s in self.sources]


@dataclass(frozen=True)
class Settings:
    """Filesystem layout. Everything hangs off the project root and data dir."""

    root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    warehouse_path: Path = PROJECT_ROOT / "data" / "warehouse.duckdb"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def manifest_path(self) -> Path:
        return self.raw_dir / "manifest.json"

    @property
    def sources_file(self) -> Path:
        return self.root / "config" / "sources.yml"

    @classmethod
    def from_env(cls, root: Path = PROJECT_ROOT) -> Settings:
        """Build settings, letting QODP_DATA_DIR and QODP_WAREHOUSE override paths."""
        data_dir = Path(os.environ.get("QODP_DATA_DIR", root / "data"))
        warehouse = Path(os.environ.get("QODP_WAREHOUSE", data_dir / "warehouse.duckdb"))
        return cls(root=root, data_dir=data_dir, warehouse_path=warehouse)


def load_catalogue(path: Path) -> Catalogue:
    """Read and validate the sources file."""
    if not path.exists():
        raise ConfigError(f"sources file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        portal = PortalConfig(**raw["portal"])
    except KeyError as exc:
        raise ConfigError("sources file needs a 'portal' section") from exc
    except TypeError as exc:
        raise ConfigError(f"bad portal section: {exc}") from exc

    sources: list[Source] = []
    seen: set[str] = set()
    for i, item in enumerate(raw.get("sources") or []):
        missing = {"key", "dataset_id", "title", "publisher"} - set(item)
        if missing:
            raise ConfigError(f"source #{i + 1} is missing {sorted(missing)}")
        key = item["key"]
        if not _KEY_PATTERN.match(key):
            raise ConfigError(f"source key '{key}' must be lower snake_case")
        if key in seen:
            raise ConfigError(f"duplicate source key '{key}'")
        seen.add(key)
        sources.append(
            Source(
                key=key,
                dataset_id=item["dataset_id"],
                title=item["title"],
                publisher=item["publisher"],
                description=" ".join(str(item.get("description", "")).split()),
                expected_columns=tuple(item.get("expected_columns") or ()),
                min_rows=int(item.get("min_rows", 1)),
            )
        )
    if not sources:
        raise ConfigError("sources file does not list any sources")
    return Catalogue(portal=portal, sources=tuple(sources))
