"""Fetch community House/Senate stock-watcher JSON dumps.

Convenience only. House Clerk and Senate eFD remain the legal source.
Bytes are written as received: disclosure_date is never renamed to trade_date.
fetched_at is wall-clock metadata, not an event time. Not a live track record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GetBytes = Callable[[str], bytes]
NowFn = Callable[[], datetime]

USER_AGENT = "congress-alpha-research/0.1"
MANIFEST_NAME = "manifest.json"
NOTE = (
    "Convenience dump of community watcher JSON. "
    "House Clerk / Senate eFD remain the legal source. "
    "Not a live track record. Event clock is disclosure_date."
)


@dataclass(frozen=True)
class WatcherSource:
    url: str
    filename: str


# Community dumps (not Clerk/eFD). CI never hits these URLs.
# Senate GitHub raw is published. House data repo may 404; fetch still
# writes whatever bytes a host returns, without renaming disclosure_date.
SOURCES: dict[str, WatcherSource] = {
    "house-watcher": WatcherSource(
        url=(
            "https://raw.githubusercontent.com/timothycarambat/"
            "house-stock-watcher-data/master/data/all_transactions.json"
        ),
        filename="house_watcher_transactions.json",
    ),
    "senate-watcher": WatcherSource(
        url=(
            "https://raw.githubusercontent.com/timothycarambat/"
            "senate-stock-watcher-data/master/aggregate/all_transactions.json"
        ),
        filename="senate_watcher_transactions.json",
    ),
}


def http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read()
    except HTTPError as exc:
        raise URLError(f"GET {url} failed: HTTP {exc.code}") from exc


def _validate_json_bytes(body: bytes) -> None:
    data = json.loads(body)
    if not isinstance(data, (list, dict)):
        raise ValueError("watcher dump must be a JSON array or object")


def fetch_watcher(
    source: str,
    out: Path | str,
    *,
    get_bytes: GetBytes | None = None,
    now: NowFn | None = None,
) -> dict:
    spec = SOURCES.get(source)
    if spec is None:
        known = ", ".join(sorted(SOURCES))
        raise ValueError(f"unknown source {source!r}; use {known}")

    getter = get_bytes or http_get
    stamp = (now or (lambda: datetime.now(timezone.utc)))()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)

    body = getter(spec.url)
    _validate_json_bytes(body)

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_path = out_dir / spec.filename
    dump_path.write_bytes(body)

    digest = hashlib.sha256(body).hexdigest()
    manifest = {
        "source": source,
        "url": spec.url,
        "fetched_at": stamp.isoformat(),
        "filename": spec.filename,
        "sha256": digest,
        "bytes": len(body),
        "note": NOTE,
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
