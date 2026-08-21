from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import URLError

import pytest

from congress_alpha.cli import main
from congress_alpha.fetch import SOURCES, fetch_watcher, http_get
from congress_alpha.ingest import ingest_watcher_json

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
MINI = FIXTURES / "watcher_dump_mini.json"
OK = FIXTURES / "trades_ok.json"
FIXED_NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _serve(path: Path):
    body = path.read_bytes()

    def get_bytes(url: str) -> bytes:
        assert url in {s.url for s in SOURCES.values()}
        return body

    return get_bytes


def test_fetch_writes_dump_and_manifest(tmp_path):
    body = MINI.read_bytes()
    manifest = fetch_watcher(
        "house-watcher",
        tmp_path,
        get_bytes=_serve(MINI),
        now=lambda: FIXED_NOW,
    )
    dump = tmp_path / "house_watcher_transactions.json"
    man_path = tmp_path / "manifest.json"
    assert dump.read_bytes() == body
    assert man_path.is_file()
    loaded = json.loads(man_path.read_text())
    assert loaded["fetched_at"] == FIXED_NOW.isoformat()
    assert loaded["url"] == SOURCES["house-watcher"].url
    assert loaded["source"] == "house-watcher"
    assert loaded["sha256"] == manifest["sha256"]
    assert loaded["sha256"] == hashlib.sha256(body).hexdigest()
    assert loaded["bytes"] == len(body)
    assert "disclosure_date" in loaded["note"]
    assert "live track record" in loaded["note"].lower()
    assert "Clerk" in loaded["note"] or "eFD" in loaded["note"]


def test_fetch_does_not_rename_disclosure_date(tmp_path):
    fetch_watcher("senate-watcher", tmp_path, get_bytes=_serve(MINI), now=lambda: FIXED_NOW)
    dumped = json.loads((tmp_path / "senate_watcher_transactions.json").read_text())
    raw = json.loads(MINI.read_text())
    assert dumped == raw
    assert "disclosure_date" in dumped[0]
    assert dumped[0]["disclosure_date"] == "2023-06-12"
    assert dumped[0]["transaction_date"] == "2023-06-01"
    assert "trade_date" not in dumped[0]
    assert "disclosure_date" not in dumped[1]
    assert dumped[1]["transaction_date"] == "2023-07-05"


def test_fetch_does_not_invent_disclosure_from_transaction_date(tmp_path):
    fetch_watcher("house-watcher", tmp_path, get_bytes=_serve(MINI), now=lambda: FIXED_NOW)
    trades, report = ingest_watcher_json(tmp_path / "house_watcher_transactions.json", "house-stock-watcher")
    reasons = {row.reason for row in report.rejected}
    assert "missing_disclosure_date" in reasons
    assert all(t.disclosure_date >= t.trade_date for t in trades)
    assert not any(t.ticker == "NVDA" and t.trade_date == date(2023, 7, 5) for t in trades)


def test_cli_fetch_uses_recorded_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "congress_alpha.fetch.http_get",
        lambda url: MINI.read_bytes(),
    )
    rc = main(["fetch", "--source", "house-watcher", "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "house_watcher_transactions.json").read_bytes() == MINI.read_bytes()
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert man["url"] == SOURCES["house-watcher"].url
    assert man["sha256"]


def test_fetch_does_not_open_socket_when_injected(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("congress_alpha.fetch.urlopen", boom)
    fetch_watcher("house-watcher", tmp_path, get_bytes=_serve(MINI), now=lambda: FIXED_NOW)
    with pytest.raises(AssertionError, match="network"):
        http_get(SOURCES["house-watcher"].url)


def test_http_get_reads_mocked_urlopen(monkeypatch):
    class Resp:
        def read(self) -> bytes:
            return b"[]"

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

    monkeypatch.setattr("congress_alpha.fetch.urlopen", lambda *_a, **_k: Resp())
    assert http_get("https://example.invalid/dump.json") == b"[]"


def test_http_get_maps_http_error(monkeypatch):
    def raise_http(*_a, **_k):
        raise URLError("blocked")

    monkeypatch.setattr("congress_alpha.fetch.urlopen", raise_http)
    with pytest.raises(URLError):
        http_get(SOURCES["senate-watcher"].url)


def test_unknown_source_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown source"):
        fetch_watcher("aws", tmp_path, get_bytes=_serve(MINI))


def test_fetch_then_run_still_watermarked(tmp_path):
    from congress_alpha.ingest import apply_ingest
    from congress_alpha.pipeline import run_from_db

    fetch_watcher("house-watcher", tmp_path, get_bytes=_serve(OK), now=lambda: FIXED_NOW)
    db = tmp_path / "fx.db"
    apply_ingest(
        db,
        trades_path=tmp_path / "house_watcher_transactions.json",
        prices_path=FIXTURES / "prices.csv",
        source="house-stock-watcher",
        politicians_path=FIXTURES / "politicians.json",
        securities_path=FIXTURES / "securities.json",
        committees_path=FIXTURES / "committees.json",
        reset=True,
    )
    brief = tmp_path / "brief.md"
    payload = run_from_db(
        db_path=db,
        dash_path=tmp_path / "dash.json",
        brief_path=brief,
        run_ablations=True,
        start=date(2023, 6, 1),
    )
    assert payload["mode"] == "ingested"
    assert "disclosure_date" in payload["disclaimer"]
    assert "not a live track record" in payload["disclaimer"].lower()
    text = brief.read_text()
    assert "INGESTED RESEARCH FILE" in text
    assert "trade_date never" in text
