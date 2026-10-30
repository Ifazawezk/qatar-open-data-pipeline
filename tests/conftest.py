"""Shared helpers. Nothing here touches the network."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.config import Catalogue, PortalConfig, Settings, Source
from pipeline.extract import Manifest, ManifestEntry, inspect_csv, sha256_bytes

FIXTURES = Path(__file__).parent / "fixtures"

TEST_PORTAL = PortalConfig(
    api_url="https://portal.test/api/explore/v2.1",
    site_url="https://portal.test",
    licence="CC BY 4.0",
    licence_url="https://creativecommons.org/licenses/by/4.0/",
)


def make_catalogue(*keys: str) -> Catalogue:
    sources = tuple(
        Source(key=k, dataset_id=k.replace("_", "-"), title=k, publisher="Test") for k in keys
    )
    return Catalogue(portal=TEST_PORTAL, sources=sources)


def write_raw(
    settings: Settings,
    key: str,
    content: bytes,
    fetched_at: str = "2026-10-01T06:00:00+00:00",
) -> None:
    """Put a raw file in place and register it in the manifest, as extract would."""
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    (settings.raw_dir / f"{key}.csv").write_bytes(content)
    header, rows = inspect_csv(content)
    manifest = Manifest(settings.manifest_path)
    manifest.put(
        ManifestEntry(
            key=key,
            dataset_id=key.replace("_", "-"),
            title=key,
            publisher="Test",
            file=f"{key}.csv",
            source_url=f"https://portal.test/{key}.csv",
            page_url=f"https://portal.test/{key}/",
            licence="CC BY 4.0",
            fetched_at=fetched_at,
            checked_at=fetched_at,
            source_modified="2026-09-01T00:00:00+00:00",
            row_count=rows,
            columns=header,
            sha256=sha256_bytes(content),
            bytes=len(content),
        )
    )
    manifest.save()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        root=tmp_path,
        data_dir=tmp_path / "data",
        warehouse_path=tmp_path / "data" / "warehouse.duckdb",
    )
