"""Optional ingest from public House/Senate stock-watcher JSON dumps.

These community datasets parse official PTRs. They are a convenience, not the
legal record. The House Clerk and Senate eFD systems remain the source.

https://disclosures-clerk.house.gov/
https://efdsearch.senate.gov/
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from congress_alpha.config import AMOUNT_BANDS
from congress_alpha.types import TradeEvent

AMOUNT_RE = re.compile(r"\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)")


def parse_amount_band(text: str | None) -> tuple[float, float]:
    if not text:
        return AMOUNT_BANDS[0]
    m = AMOUNT_RE.search(text.replace(",", ""))
    if not m:
        # try already-stripped
        m = AMOUNT_RE.search(text)
    if not m:
        return AMOUNT_BANDS[0]
    lo = float(m.group(1).replace(",", ""))
    hi = float(m.group(2).replace(",", ""))
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _side(raw: str | None) -> str | None:
    if not raw:
        return None
    u = raw.lower()
    if "purchase" in u or u == "buy":
        return "BUY"
    if "sale" in u or "sell" in u or "sold" in u:
        return "SELL"
    if "exchange" in u:
        return None
    return None


def load_watcher_json(path: Path, source: str) -> list[TradeEvent]:
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = data.get("transactions") or data.get("data") or []
    out: list[TradeEvent] = []
    for i, row in enumerate(data):
        ticker = (row.get("ticker") or row.get("symbol") or "").strip().upper()
        if not ticker or ticker in {"--", "N/A", "NONE"}:
            continue
        # skip options / bonds / funds with obvious suffixes
        if any(x in ticker for x in ("CALL", "PUT", " ", "^")):
            continue
        tdate = _parse_date(row.get("transaction_date") or row.get("trade_date"))
        ddate = _parse_date(row.get("disclosure_date") or row.get("filed_date"))
        if not tdate or not ddate or ddate < tdate:
            continue
        side = _side(row.get("type") or row.get("transaction_type") or row.get("side"))
        if side is None:
            continue
        lo, hi = parse_amount_band(str(row.get("amount") or row.get("range") or ""))
        pid = (
            row.get("representative")
            or row.get("senator")
            or row.get("name")
            or f"unknown-{i}"
        )
        pid_key = re.sub(r"[^a-z0-9]+", "-", pid.lower()).strip("-")
        out.append(
            TradeEvent(
                trade_id=f"{source}-{i:06d}",
                politician_id=pid_key,
                ticker=ticker,
                trade_date=tdate,
                disclosure_date=ddate,
                side=side,
                amount_min=lo,
                amount_max=hi,
                owner=str(row.get("owner") or "self"),
                source=source,
            )
        )
    return out
