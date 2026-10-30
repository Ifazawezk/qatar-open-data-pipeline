"""Download raw datasets from the portal.

Each dataset costs at most two requests: one for its metadata and one for the
CSV export. A file is reused without any request while it is younger than
cache_ttl_hours, and after that it is only downloaded again when the portal
reports that the data changed (metadata field data_processed).

Raw files are written unchanged to data/raw/<key>.csv. data/raw/manifest.json
records where every file came from, when it was fetched, its row count and its
SHA-256 hash so later steps (and people) can trust what they are reading.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipeline.config import Catalogue, PortalConfig, Settings, Source

log = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class ExtractError(RuntimeError):
    """A dataset could not be downloaded or failed a basic sanity check."""


class SchemaChangedError(ExtractError):
    """The export no longer has the columns the models depend on."""


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def inspect_csv(content: bytes) -> tuple[list[str], int]:
    """Return the header and the number of data rows of a CSV export.

    Uses the csv module rather than counting lines because quoted values in the
    portal exports can contain line breaks.
    """
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = [name.strip() for name in next(reader)]
    except StopIteration as exc:
        raise ExtractError("export is empty") from exc
    rows = sum(1 for row in reader if row)
    return header, rows


def _write_atomic(path: Path, content: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, path)


@dataclass
class ManifestEntry:
    key: str
    dataset_id: str
    title: str
    publisher: str
    file: str
    source_url: str
    page_url: str
    licence: str
    fetched_at: str
    checked_at: str
    source_modified: str | None
    row_count: int
    columns: list[str] = field(default_factory=list)
    sha256: str = ""
    bytes: int = 0
    portal_records_count: int | None = None


class Manifest:
    """JSON file with one entry per source, keyed by source key."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, ManifestEntry] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, item in data.get("sources", {}).items():
                self.entries[key] = ManifestEntry(**item)

    def get(self, key: str) -> ManifestEntry | None:
        return self.entries.get(key)

    def put(self, entry: ManifestEntry) -> None:
        self.entries[entry.key] = entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": utc_now().isoformat(),
            "sources": {key: asdict(self.entries[key]) for key in sorted(self.entries)},
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        _write_atomic(self.path, text.encode("utf-8"))


class PortalClient:
    """Thin wrapper around requests with pacing and retries.

    sleep and clock are injectable so tests can run without waiting.
    """

    def __init__(
        self,
        portal: PortalConfig,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.portal = portal
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", portal.user_agent)
        self.sleep = sleep
        self.clock = clock
        self.request_count = 0
        self._last_request_at: float | None = None

    def _wait_turn(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = self.clock() - self._last_request_at
        remaining = self.portal.request_delay_seconds - elapsed
        if remaining > 0:
            self.sleep(remaining)

    def _retry_delay(self, attempt: int, response: requests.Response | None) -> float:
        if response is not None:
            header = response.headers.get("Retry-After", "")
            if header.isdigit():
                return float(header)
        return self.portal.backoff_seconds * 2 ** (attempt - 1)

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        attempts = self.portal.max_retries + 1
        problem = ""
        for attempt in range(1, attempts + 1):
            self._wait_turn()
            response: requests.Response | None = None
            try:
                self.request_count += 1
                response = self.session.get(url, params=params, timeout=self.portal.timeout_seconds)
            except (requests.ConnectionError, requests.Timeout) as exc:
                problem = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 400:
                    remaining = response.headers.get("X-RateLimit-Remaining")
                    if remaining is not None:
                        log.debug("rate limit remaining: %s", remaining)
                    return response
                problem = f"HTTP {response.status_code}"
                if response.status_code not in RETRYABLE_STATUS:
                    raise ExtractError(f"{url} returned {problem}")
            finally:
                self._last_request_at = self.clock()

            if attempt == attempts:
                break
            delay = self._retry_delay(attempt, response)
            log.warning(
                "request failed (%s), attempt %d of %d, retrying in %.1fs",
                problem,
                attempt,
                attempts,
                delay,
            )
            self.sleep(delay)
        raise ExtractError(f"giving up on {url} after {attempts} attempts ({problem})")

    def dataset_metadata(self, source: Source) -> dict:
        return self.get(source.metadata_url(self.portal)).json()

    def export_csv(self, source: Source) -> requests.Response:
        return self.get(source.export_url(self.portal), params={"delimiter": ","})


def _summarise_metadata(meta: dict) -> dict:
    """Keep the parts of the portal metadata that the docs and models use."""
    default = meta.get("metas", {}).get("default", {})
    return {
        "dataset_id": meta.get("dataset_id"),
        "title": default.get("title"),
        "title_ar": default.get("title_ar"),
        "publisher": default.get("publisher"),
        "licence": default.get("license"),
        "modified": default.get("modified"),
        "data_processed": default.get("data_processed"),
        "records_count": default.get("records_count"),
        "fields": [
            {
                "name": f.get("name"),
                "type": f.get("type"),
                "label_en": f.get("label_en") or f.get("label"),
                "label_ar": f.get("label_ar"),
            }
            for f in meta.get("fields", [])
        ],
    }


def _source_version(meta: dict) -> str | None:
    default = meta.get("metas", {}).get("default", {})
    return default.get("data_processed") or default.get("modified")


@dataclass
class ExtractResult:
    key: str
    status: str  # downloaded | unchanged | cached
    row_count: int
    bytes: int
    fetched_at: str

    @classmethod
    def reused(cls, entry: ManifestEntry, status: str) -> ExtractResult:
        return cls(entry.key, status, entry.row_count, entry.bytes, entry.fetched_at)


def extract_source(
    source: Source,
    catalogue: Catalogue,
    settings: Settings,
    client: PortalClient,
    manifest: Manifest,
    force: bool = False,
    now: datetime | None = None,
) -> ExtractResult:
    now = now or utc_now()
    portal = catalogue.portal
    raw_path = settings.raw_dir / f"{source.key}.csv"
    meta_path = settings.raw_dir / f"{source.key}.meta.json"
    entry = manifest.get(source.key)

    file_ok = entry is not None and raw_path.exists() and sha256_file(raw_path) == entry.sha256
    if entry is not None and raw_path.exists() and not file_ok:
        log.warning("%s: raw file does not match the manifest hash, downloading again", source.key)

    if file_ok and not force:
        age_hours = (now - datetime.fromisoformat(entry.checked_at)).total_seconds() / 3600
        if age_hours < portal.cache_ttl_hours:
            log.info("%s: cached copy is %.1fh old, skipping", source.key, age_hours)
            return ExtractResult.reused(entry, "cached")

    meta = client.dataset_metadata(source)
    version = _source_version(meta)

    if file_ok and not force and version is not None and version == entry.source_modified:
        log.info("%s: unchanged on the portal since %s", source.key, version)
        entry.checked_at = now.isoformat()
        manifest.put(entry)
        return ExtractResult.reused(entry, "unchanged")

    response = client.export_csv(source)
    content = response.content
    header, row_count = inspect_csv(content)

    missing = [c for c in source.expected_columns if c not in header]
    if missing:
        raise SchemaChangedError(
            f"{source.key}: export is missing expected columns {missing}; got {header}"
        )
    if row_count < source.min_rows:
        raise ExtractError(
            f"{source.key}: export has {row_count} rows, expected at least {source.min_rows}"
        )
    portal_count = meta.get("metas", {}).get("default", {}).get("records_count")
    if portal_count is not None and portal_count != row_count:
        log.warning(
            "%s: portal reports %s records but the export has %s rows",
            source.key,
            portal_count,
            row_count,
        )

    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(raw_path, content)
    meta_text = json.dumps(_summarise_metadata(meta), indent=2, ensure_ascii=False) + "\n"
    _write_atomic(meta_path, meta_text.encode("utf-8"))

    manifest.put(
        ManifestEntry(
            key=source.key,
            dataset_id=source.dataset_id,
            title=source.title,
            publisher=source.publisher,
            file=raw_path.name,
            source_url=response.url,
            page_url=source.page_url(portal),
            licence=portal.licence,
            fetched_at=now.isoformat(),
            checked_at=now.isoformat(),
            source_modified=version,
            row_count=row_count,
            columns=header,
            sha256=sha256_bytes(content),
            bytes=len(content),
            portal_records_count=portal_count,
        )
    )
    log.info("%s: downloaded %d rows (%d bytes)", source.key, row_count, len(content))
    return ExtractResult(source.key, "downloaded", row_count, len(content), now.isoformat())


def extract_all(
    settings: Settings,
    catalogue: Catalogue,
    keys: Iterable[str] | None = None,
    force: bool = False,
    client: PortalClient | None = None,
    now: datetime | None = None,
) -> list[ExtractResult]:
    """Extract the selected sources (all by default) and save the manifest.

    The manifest is saved after every source, so a failure halfway through
    keeps the record of what was already fetched.
    """
    sources = [catalogue.get(k) for k in keys] if keys else list(catalogue.sources)
    client = client or PortalClient(catalogue.portal)
    manifest = Manifest(settings.manifest_path)
    results = []
    for source in sources:
        results.append(extract_source(source, catalogue, settings, client, manifest, force, now))
        manifest.save()
    log.info("extract finished: %d sources, %d requests", len(results), client.request_count)
    return results
