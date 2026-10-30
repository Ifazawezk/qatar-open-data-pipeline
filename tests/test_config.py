from pathlib import Path

import pytest

from pipeline.config import PROJECT_ROOT, ConfigError, Settings, load_catalogue

PORTAL = """
portal:
  api_url: https://example.org/api/explore/v2.1
  site_url: https://example.org
  licence: CC BY 4.0
  licence_url: https://creativecommons.org/licenses/by/4.0/
"""


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sources.yml"
    path.write_text(PORTAL + body, encoding="utf-8")
    return path


def test_project_sources_file_is_valid():
    catalogue = load_catalogue(PROJECT_ROOT / "config" / "sources.yml")
    assert len(catalogue.sources) >= 4
    assert len(set(catalogue.keys)) == len(catalogue.keys)
    for source in catalogue.sources:
        assert source.expected_columns, f"{source.key} has no column contract"


def test_urls_are_built_from_portal_settings(tmp_path):
    path = write(
        tmp_path,
        "sources:\n  - {key: cpi, dataset_id: cpi-monthly, title: CPI, publisher: NPC}\n",
    )
    catalogue = load_catalogue(path)
    source = catalogue.get("cpi")
    assert source.export_url(catalogue.portal) == (
        "https://example.org/api/explore/v2.1/catalog/datasets/cpi-monthly/exports/csv"
    )
    assert source.page_url(catalogue.portal) == "https://example.org/explore/dataset/cpi-monthly/"


@pytest.mark.parametrize(
    "body, message",
    [
        ("sources: []\n", "does not list any sources"),
        ("sources:\n  - {key: a, title: x, publisher: y}\n", "missing"),
        ("sources:\n  - {key: Bad-Key, dataset_id: d, title: x, publisher: y}\n", "snake_case"),
        (
            "sources:\n"
            "  - {key: a, dataset_id: d, title: x, publisher: y}\n"
            "  - {key: a, dataset_id: e, title: x, publisher: y}\n",
            "duplicate",
        ),
    ],
)
def test_invalid_sources_are_rejected(tmp_path, body, message):
    with pytest.raises(ConfigError, match=message):
        load_catalogue(write(tmp_path, body))


def test_unknown_source_key_lists_known_keys(tmp_path):
    path = write(tmp_path, "sources:\n  - {key: a, dataset_id: d, title: x, publisher: y}\n")
    with pytest.raises(ConfigError, match="Known sources: a"):
        load_catalogue(path).get("missing")


def test_settings_respect_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("QODP_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.delenv("QODP_WAREHOUSE", raising=False)
    settings = Settings.from_env()
    assert settings.raw_dir == tmp_path / "d" / "raw"
    assert settings.warehouse_path == tmp_path / "d" / "warehouse.duckdb"
