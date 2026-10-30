import json
from datetime import UTC, datetime, timedelta

import pytest
import requests
import responses

from pipeline.config import Catalogue, PortalConfig, Settings, Source
from pipeline.extract import (
    ExtractError,
    Manifest,
    PortalClient,
    SchemaChangedError,
    extract_all,
    inspect_csv,
    sha256_bytes,
)

API = "https://portal.test/api/explore/v2.1"
CSV = "\ufeffyear,zone_number,value\n2024,1,100\n2024,2,200\n2025,1,150\n".encode()
NOW = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)


def metadata(version="2026-01-01T00:00:00+00:00", records=3):
    return {
        "dataset_id": "water",
        "fields": [{"name": "year", "type": "date", "label_en": "Year", "label_ar": "السنة"}],
        "metas": {
            "default": {
                "title": "Water",
                "title_ar": "المياه",
                "data_processed": version,
                "records_count": records,
                "license": "CC BY",
            }
        },
    }


@pytest.fixture
def catalogue():
    portal = PortalConfig(
        api_url=API,
        site_url="https://portal.test",
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        request_delay_seconds=1.0,
        max_retries=2,
        backoff_seconds=0.25,
        cache_ttl_hours=24,
    )
    source = Source(
        key="water",
        dataset_id="water-total",
        title="Water",
        publisher="KAHRAMAA",
        expected_columns=("year", "zone_number", "value"),
        min_rows=2,
    )
    return Catalogue(portal=portal, sources=(source,))


@pytest.fixture
def settings(tmp_path):
    return Settings(root=tmp_path, data_dir=tmp_path / "data")


@pytest.fixture
def waits():
    return []


@pytest.fixture
def client(catalogue, waits):
    return PortalClient(catalogue.portal, sleep=waits.append, clock=lambda: 0.0)


META_URL = f"{API}/catalog/datasets/water-total"
EXPORT_URL = f"{API}/catalog/datasets/water-total/exports/csv"


def mock_portal(rsps, version="2026-01-01T00:00:00+00:00", body=CSV):
    rsps.get(META_URL, json=metadata(version))
    rsps.get(EXPORT_URL, body=body, content_type="text/csv")


def test_inspect_csv_handles_bom_and_quoted_newlines():
    content = '\ufeffa,b\n1,"two\nlines"\n3,4\n'.encode()
    header, rows = inspect_csv(content)
    assert header == ["a", "b"]
    assert rows == 2


@responses.activate
def test_download_writes_raw_file_metadata_and_manifest(catalogue, settings, client):
    mock_portal(responses)
    [result] = extract_all(settings, catalogue, client=client, now=NOW)

    assert result.status == "downloaded"
    assert (settings.raw_dir / "water.csv").read_bytes() == CSV
    meta = json.loads((settings.raw_dir / "water.meta.json").read_text(encoding="utf-8"))
    assert meta["title_ar"] == "المياه"
    assert meta["fields"][0]["label_ar"] == "السنة"

    entry = Manifest(settings.manifest_path).get("water")
    assert entry.row_count == 3
    assert entry.sha256 == sha256_bytes(CSV)
    assert entry.columns == ["year", "zone_number", "value"]
    assert entry.source_url == f"{EXPORT_URL}?delimiter=%2C"
    assert entry.fetched_at == NOW.isoformat()
    assert entry.licence == "CC BY 4.0"


@responses.activate
def test_fresh_cache_makes_no_requests(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)
    calls = len(responses.calls)

    [result] = extract_all(settings, catalogue, client=client, now=NOW + timedelta(hours=2))
    assert result.status == "cached"
    assert len(responses.calls) == calls


@responses.activate
def test_unchanged_dataset_only_costs_a_metadata_request(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)

    later = NOW + timedelta(days=3)
    [result] = extract_all(settings, catalogue, client=client, now=later)
    assert result.status == "unchanged"
    assert [c.request.url.split("?")[0] for c in responses.calls][-1] == META_URL
    assert Manifest(settings.manifest_path).get("water").checked_at == later.isoformat()


@responses.activate
def test_changed_dataset_is_downloaded_again(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)

    responses.reset()
    newer = CSV + b"2025,2,250\n"
    mock_portal(responses, version="2026-02-01T00:00:00+00:00", body=newer)
    [result] = extract_all(settings, catalogue, client=client, now=NOW + timedelta(days=3))
    assert result.status == "downloaded"
    assert result.row_count == 4


@responses.activate
def test_force_ignores_the_cache(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)
    [result] = extract_all(settings, catalogue, client=client, now=NOW, force=True)
    assert result.status == "downloaded"


@responses.activate
def test_edited_raw_file_is_replaced(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)
    (settings.raw_dir / "water.csv").write_text("year,zone_number,value\n", encoding="utf-8")

    [result] = extract_all(settings, catalogue, client=client, now=NOW + timedelta(hours=1))
    assert result.status == "downloaded"
    assert (settings.raw_dir / "water.csv").read_bytes() == CSV


@responses.activate
def test_retries_server_errors_with_backoff(catalogue, settings, client, waits):
    responses.get(META_URL, status=503)
    responses.get(META_URL, status=502)
    responses.get(META_URL, json=metadata())
    responses.get(EXPORT_URL, body=CSV)

    [result] = extract_all(settings, catalogue, client=client, now=NOW)
    assert result.status == "downloaded"
    # exponential backoff (0.25s, 0.5s) on top of the 1s polite delay between requests
    assert [w for w in waits if w != 1.0] == [0.25, 0.5]
    assert waits.count(1.0) == 3


@responses.activate
def test_retry_after_header_is_respected(catalogue, settings, client, waits):
    responses.get(META_URL, status=429, headers={"Retry-After": "7"})
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)
    assert 7.0 in waits


@responses.activate
def test_connection_errors_are_retried(catalogue, settings, client):
    responses.get(META_URL, body=requests.ConnectionError("reset by peer"))
    mock_portal(responses)
    [result] = extract_all(settings, catalogue, client=client, now=NOW)
    assert result.status == "downloaded"


@responses.activate
def test_gives_up_after_max_retries(catalogue, settings, client):
    for _ in range(3):
        responses.get(META_URL, status=500)
    with pytest.raises(ExtractError, match="after 3 attempts"):
        extract_all(settings, catalogue, client=client, now=NOW)


@responses.activate
def test_client_errors_are_not_retried(catalogue, settings, client):
    responses.get(META_URL, status=404)
    with pytest.raises(ExtractError, match="HTTP 404"):
        extract_all(settings, catalogue, client=client, now=NOW)
    assert len(responses.calls) == 1


@responses.activate
def test_schema_change_stops_and_keeps_the_old_file(catalogue, settings, client):
    mock_portal(responses)
    extract_all(settings, catalogue, client=client, now=NOW)

    responses.reset()
    mock_portal(responses, version="v2", body=b"year,zone,value\n2024,1,100\n2024,2,200\n")
    with pytest.raises(SchemaChangedError, match="zone_number"):
        extract_all(settings, catalogue, client=client, now=NOW + timedelta(days=2))
    assert (settings.raw_dir / "water.csv").read_bytes() == CSV


@responses.activate
def test_too_few_rows_is_an_error(catalogue, settings, client):
    mock_portal(responses, body=b"year,zone_number,value\n2024,1,100\n")
    with pytest.raises(ExtractError, match="expected at least 2"):
        extract_all(settings, catalogue, client=client, now=NOW)
    assert not (settings.raw_dir / "water.csv").exists()
