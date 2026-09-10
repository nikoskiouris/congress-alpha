"""Fetch a frozen adj-close snapshot for tickers in a trades dump.

Convenience prices only. Not a live book. Warehouse stays SQLite.
fetched_at is wall-clock metadata, not an event time.
The job never rewrites the trades dump, never renames disclosure_date,
and never fills missing sessions on trade_date.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from congress_alpha.config import BENCHMARK

GetBytes = Callable[[str], bytes]
NowFn = Callable[[], datetime]

USER_AGENT = "congress-alpha-research/0.1"
CSV_NAME = "prices.csv"
MANIFEST_NAME = "manifest.json"
RAW_DIR = "raw"
SOURCE_NAME = "yahoo-adj-close"
# Wide vendor window. Not derived from trade_date or wall-clock now().
PERIOD1 = 0
PERIOD2 = 4_102_444_800  # 2100-01-01 UTC
_MISSING_TICKERS = {"", "--", "N/A", "NONE"}
NOTE = (
    "Convenience adj-close snapshot. Not a live track record. "
    "House Clerk / Senate eFD remain the legal source. "
    "Warehouse is SQLite. Event clock is disclosure_date. "
    "fetched_at is wall-clock metadata, not event time. "
    "Missing sessions are omitted, not filled on trade_date."
)


def http_get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read()
    except HTTPError as exc:
        raise URLError(f"GET {url} failed: HTTP {exc.code}") from exc


def price_url(ticker: str) -> str:
    token = quote(ticker, safe="-._")
    return (
        f"https://query1.finance.yahoo.com/v7/finance/download/{token}"
        f"?period1={PERIOD1}&period2={PERIOD2}&interval=1d"
        f"&events=history&includeAdjustedClose=true"
    )


def _json_rows(path: Path) -> list:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("transactions", "data"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def _complex_ticker(ticker: str) -> bool:
    return any(token in ticker for token in ("CALL", "PUT", " ", "^"))


def tickers_from_trades(path: Path | str) -> list[str]:
    """Tickers listed in a dump. Does not invent disclosure_date."""
    found: set[str] = {BENCHMARK}
    for row in _json_rows(Path(path)):
        if not isinstance(row, dict):
            continue
        ticker = (row.get("ticker") or row.get("symbol") or "").strip().upper()
        if ticker in _MISSING_TICKERS or _complex_ticker(ticker):
            continue
        found.add(ticker)
    return sorted(found)


def _norm_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def parse_adj_close_csv(body: bytes, default_ticker: str) -> list[tuple[str, str, str]]:
    """Parse vendor or warehouse CSV. Skip empty adj_close. Do not fill holes."""
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[str, str, str]] = []
    for raw in reader:
        if not raw:
            continue
        normalized = {_norm_header(k or ""): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        ticker = (normalized.get("ticker") or default_ticker or "").strip().upper()
        session = str(normalized.get("date") or "")[:10]
        px = normalized.get("adj_close")
        if px in (None, ""):
            px = normalized.get("close")
        if not ticker or not session or px in (None, "", "null", "none"):
            continue
        try:
            datetime.strptime(session, "%Y-%m-%d")
            float(px)
        except ValueError:
            continue
        rows.append((ticker, session, str(px)))
    return rows


def _write_prices_csv(path: Path, rows: list[tuple[str, str, str]]) -> bytes:
    ordered = sorted(rows, key=lambda r: (r[0], r[1]))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["ticker", "date", "adj_close"])
    writer.writerows(ordered)
    payload = buf.getvalue().encode("utf-8")
    path.write_bytes(payload)
    return payload


def fetch_prices(
    trades_path: Path | str,
    out: Path | str,
    *,
    get_bytes: GetBytes | None = None,
    now: NowFn | None = None,
) -> dict:
    trades = Path(trades_path)
    if not trades.is_file():
        raise FileNotFoundError(f"trades file not found: {trades}")
    trades_body = trades.read_bytes()
    trades_sha = hashlib.sha256(trades_body).hexdigest()
    tickers = tickers_from_trades(trades)
    if not tickers:
        raise ValueError("no tickers in trades dump")

    getter = get_bytes or http_get
    stamp = (now or (lambda: datetime.now(timezone.utc)))()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)

    out_dir = Path(out)
    raw_dir = out_dir / RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    urls: dict[str, str] = {}
    raw_sha: dict[str, str] = {}
    combined: list[tuple[str, str, str]] = []
    empty: list[str] = []

    for ticker in tickers:
        url = price_url(ticker)
        urls[ticker] = url
        body = getter(url)
        raw_path = raw_dir / f"{ticker}.csv"
        raw_path.write_bytes(body)
        raw_sha[ticker] = hashlib.sha256(body).hexdigest()
        parsed = parse_adj_close_csv(body, ticker)
        if not parsed:
            empty.append(ticker)
            continue
        combined.extend(parsed)

    if not combined:
        raise ValueError("no adj_close rows in snapshot")

    csv_path = out_dir / CSV_NAME
    csv_bytes = _write_prices_csv(csv_path, combined)
    digest = hashlib.sha256(csv_bytes).hexdigest()

    if trades.read_bytes() != trades_body:
        raise RuntimeError("trades dump mutated; disclosure_date must stay frozen")

    manifest = {
        "source": SOURCE_NAME,
        "fetched_at": stamp.isoformat(),
        "filename": CSV_NAME,
        "sha256": digest,
        "bytes": len(csv_bytes),
        "tickers": tickers,
        "urls": urls,
        "raw_sha256": raw_sha,
        "empty_tickers": empty,
        "trades_path": str(trades),
        "trades_sha256": trades_sha,
        "note": NOTE,
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
