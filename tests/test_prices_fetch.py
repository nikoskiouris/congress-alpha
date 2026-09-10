from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.error import URLError

import pytest

from congress_alpha.cli import main
from congress_alpha.prices_fetch import (
    SOURCE_NAME,
    fetch_prices,
    http_get,
    parse_adj_close_csv,
    price_url,
    tickers_from_trades,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
MINI_YAHOO = FIXTURES / "yahoo_adj_close_mini.csv"
MINI_DUMP = FIXTURES / "watcher_dump_mini.json"
OK = FIXTURES / "trades_ok.json"
PRICES = FIXTURES / "prices.csv"
FIXED_NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _serve_mini():
    body = MINI_YAHOO.read_bytes()

    def get_bytes(url: str) -> bytes:
        assert "query1.finance.yahoo.com" in url
        assert "finance/download/" in url
        return body

    return get_bytes


def _yahoo_from_warehouse(ticker: str) -> bytes:
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"])
    with PRICES.open() as handle:
        for row in csv.DictReader(handle):
            if (row.get("ticker") or "").upper() != ticker:
                continue
            px = row["adj_close"]
            vol = row.get("volume") or ""
            writer.writerow([row["date"], px, px, px, px, px, vol])
    return buf.getvalue().encode("utf-8")


def _serve_warehouse_yahoo():
    def get_bytes(url: str) -> bytes:
        ticker = url.split("/download/", 1)[1].split("?", 1)[0]
        body = _yahoo_from_warehouse(ticker)
        assert body.count(b"\n") > 2
        return body

    return get_bytes


def test_tickers_include_spy_skip_options():
    tickers = tickers_from_trades(MINI_DUMP)
    assert "LMT" in tickers
    assert "NVDA" in tickers
    assert "SPY" in tickers
    dirty = FIXTURES / "trades_dirty.json"
    skipped = tickers_from_trades(dirty)
    assert "NVDA CALL" not in skipped
    assert "" not in skipped
    assert all("CALL" not in t and "PUT" not in t and " " not in t for t in skipped)


def test_fetch_prices_writes_csv_and_manifest(tmp_path):
    trades = tmp_path / "trades.json"
    trades.write_bytes(MINI_DUMP.read_bytes())
    before = trades.read_bytes()
    manifest = fetch_prices(
        trades,
        tmp_path / "out",
        get_bytes=_serve_mini(),
        now=lambda: FIXED_NOW,
    )
    out = tmp_path / "out"
    csv_path = out / "prices.csv"
    man_path = out / "manifest.json"
    assert csv_path.is_file()
    assert man_path.is_file()
    loaded = json.loads(man_path.read_text())
    assert loaded["fetched_at"] == FIXED_NOW.isoformat()
    assert loaded["source"] == SOURCE_NAME
    assert loaded["filename"] == "prices.csv"
    assert loaded["sha256"] == manifest["sha256"]
    assert loaded["sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert loaded["trades_sha256"] == hashlib.sha256(before).hexdigest()
    assert loaded["tickers"] == ["LMT", "NVDA", "SPY"]
    assert "disclosure_date" in loaded["note"]
    assert "live track record" in loaded["note"].lower()
    assert "SQLite" in loaded["note"] or "sqlite" in loaded["note"].lower()
    assert trades.read_bytes() == before
    raw_lmt = (out / "raw" / "LMT.csv").read_bytes()
    assert raw_lmt == MINI_YAHOO.read_bytes()
    assert loaded["raw_sha256"]["LMT"] == hashlib.sha256(raw_lmt).hexdigest()


def test_fetch_prices_does_not_rename_disclosure_or_fill_trade_date(tmp_path):
    trades = tmp_path / "trades.json"
    trades.write_bytes(MINI_DUMP.read_bytes())
    fetch_prices(trades, tmp_path / "out", get_bytes=_serve_mini(), now=lambda: FIXED_NOW)
    dumped = json.loads(trades.read_text())
    raw = json.loads(MINI_DUMP.read_text())
    assert dumped == raw
    assert dumped[0]["disclosure_date"] == "2023-06-12"
    assert dumped[0]["transaction_date"] == "2023-06-01"
    assert "trade_date" not in dumped[0]
    rows = list(csv.DictReader((tmp_path / "out" / "prices.csv").open()))
    dates = {r["date"] for r in rows}
    # Vendor mini starts 2023-06-05; do not invent the trade_date session.
    assert "2023-06-01" not in dates
    assert dates == {"2023-06-05", "2023-06-12"}
    assert {r["ticker"] for r in rows} == {"LMT", "NVDA", "SPY"}
    assert list(rows[0].keys()) == ["ticker", "date", "adj_close"]


def test_parse_skips_null_adj_close_no_fill():
    body = (
        "Date,Open,High,Low,Close,Adj Close,Volume\n"
        "2023-06-05,1,1,1,1,1.5,10\n"
        "2023-06-06,1,1,1,1,null,10\n"
        "2023-06-07,1,1,1,1,,10\n"
    ).encode()
    rows = parse_adj_close_csv(body, "LMT")
    assert rows == [("LMT", "2023-06-05", "1.5")]


def test_parse_stooq_close_when_no_adj_close_column():
    body = (
        "Date,Open,High,Low,Close,Volume\n"
        "2023-06-05,1,1,1,2.25,10\n"
        "2023-06-06,1,1,1,,10\n"
    ).encode()
    rows = parse_adj_close_csv(body, "SPY")
    assert rows == [("SPY", "2023-06-05", "2.25")]


def test_cli_fetch_prices_uses_recorded_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "congress_alpha.prices_fetch.http_get",
        lambda url: MINI_YAHOO.read_bytes(),
    )
    trades = tmp_path / "trades.json"
    trades.write_bytes(OK.read_bytes())
    out = tmp_path / "px"
    rc = main(["fetch-prices", "--trades", str(trades), "--out", str(out)])
    assert rc == 0
    assert (out / "prices.csv").is_file()
    man = json.loads((out / "manifest.json").read_text())
    assert man["source"] == SOURCE_NAME
    assert man["sha256"]
    assert "SPY" in man["tickers"]
    assert set(man["tickers"]) >= {"LMT", "NVDA", "JPM", "SPY"}


def test_fetch_prices_does_not_open_socket_when_injected(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("congress_alpha.prices_fetch.urlopen", boom)
    fetch_prices(
        MINI_DUMP,
        tmp_path,
        get_bytes=_serve_mini(),
        now=lambda: FIXED_NOW,
    )
    with pytest.raises(AssertionError, match="network"):
        http_get(price_url("SPY"))


def test_http_get_maps_http_error(monkeypatch):
    def raise_http(*_a, **_k):
        raise URLError("blocked")

    monkeypatch.setattr("congress_alpha.prices_fetch.urlopen", raise_http)
    with pytest.raises(URLError):
        http_get(price_url("SPY"))


def test_missing_trades_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        fetch_prices(tmp_path / "nope.json", tmp_path, get_bytes=_serve_mini())


def test_url_not_built_from_trade_date():
    url = price_url("LMT")
    assert "LMT" in url
    assert "2023-06-01" not in url
    assert "trade_date" not in url
    assert "disclosure_date" not in url


def test_fetch_prices_then_run_still_watermarked(tmp_path):
    from congress_alpha.ingest import apply_ingest
    from congress_alpha.pipeline import run_from_db

    trades = tmp_path / "trades.json"
    trades.write_bytes(OK.read_bytes())
    px_dir = tmp_path / "px"
    fetch_prices(
        trades,
        px_dir,
        get_bytes=_serve_warehouse_yahoo(),
        now=lambda: FIXED_NOW,
    )
    db = tmp_path / "fx.db"
    apply_ingest(
        db,
        trades_path=trades,
        prices_path=px_dir / "prices.csv",
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
    assert trades.read_bytes() == OK.read_bytes()
