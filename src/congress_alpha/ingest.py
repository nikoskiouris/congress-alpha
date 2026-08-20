"""Optional ingest from public House/Senate stock-watcher JSON dumps.

These community datasets parse official PTRs. They are a convenience, not the
legal record. The House Clerk and Senate eFD systems remain the source.

https://disclosures-clerk.house.gov/
https://efdsearch.senate.gov/
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from congress_alpha.config import AMOUNT_BANDS
from congress_alpha.types import Committee, Politician, Security, TradeEvent
from congress_alpha.warehouse import (
    connect,
    fetch_politicians,
    fetch_securities,
    init_db,
    insert_prices,
    insert_trades,
    reset_db,
    upsert_committees,
    upsert_politicians,
    upsert_securities,
)

AMOUNT_RE = re.compile(r"\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)")
_MISSING_TICKERS = {"", "--", "N/A", "NONE"}


@dataclass
class RejectedRow:
    index: int
    reason: str
    detail: str = ""


@dataclass
class IngestReport:
    source: str
    n_read: int
    n_accepted: int
    n_rejected: int
    rejected: list[RejectedRow]
    politicians_upserted: int = 0
    securities_unmapped: list[str] = field(default_factory=list)
    disclosure_min: date | None = None
    disclosure_max: date | None = None
    note: str = "Signals may only use disclosure_date as event time."

    def as_public_dict(self) -> dict:
        return {
            "source": self.source,
            "n_read": self.n_read,
            "n_accepted": self.n_accepted,
            "n_rejected": self.n_rejected,
            "rejected": [asdict(row) for row in self.rejected],
            "politicians_upserted": self.politicians_upserted,
            "securities_unmapped": list(self.securities_unmapped),
            "disclosure_min": self.disclosure_min.isoformat() if self.disclosure_min else None,
            "disclosure_max": self.disclosure_max.isoformat() if self.disclosure_max else None,
            "note": self.note,
        }


def try_parse_amount_band(text: str | None) -> tuple[float, float] | None:
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    m = AMOUNT_RE.search(text.replace(",", ""))
    if not m:
        m = AMOUNT_RE.search(text)
    if not m:
        return None
    lo = float(m.group(1).replace(",", ""))
    hi = float(m.group(2).replace(",", ""))
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def parse_amount_band(text: str | None) -> tuple[float, float]:
    parsed = try_parse_amount_band(text)
    if parsed is None:
        return AMOUNT_BANDS[0]
    return parsed


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = str(value).strip()[:10]
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


def _json_rows(path: Path, *keys: str) -> list:
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    return []


def _politician_id(raw_name: object, index: int) -> str:
    pid = str(raw_name).strip() if raw_name else ""
    if not pid:
        pid = f"unknown-{index}"
    return re.sub(r"[^a-z0-9]+", "-", pid.lower()).strip("-")


def _name_from_id(politician_id: str) -> str:
    return politician_id.replace("-", " ").title()


def _trade_index(trade_id: str, source: str) -> int:
    prefix = f"{source}-"
    if trade_id.startswith(prefix):
        return int(trade_id[len(prefix) :])
    return int(trade_id.rsplit("-", 1)[-1])


def _disclosure_bounds(trades: list[TradeEvent]) -> tuple[date | None, date | None]:
    if not trades:
        return None, None
    dates = [t.disclosure_date for t in trades]
    return min(dates), max(dates)


def ingest_watcher_json(path: Path | str, source: str) -> tuple[list[TradeEvent], IngestReport]:
    rows = _json_rows(Path(path), "transactions", "data")
    accepted: list[TradeEvent] = []
    rejected: list[RejectedRow] = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            rejected.append(RejectedRow(i, "missing_ticker", "row is not an object"))
            continue

        ticker = (row.get("ticker") or row.get("symbol") or "").strip().upper()
        if ticker in _MISSING_TICKERS:
            rejected.append(RejectedRow(i, "missing_ticker", ticker))
            continue
        if any(token in ticker for token in ("CALL", "PUT", " ", "^")):
            rejected.append(RejectedRow(i, "options_or_complex", ticker))
            continue

        tdate = _parse_date(row.get("transaction_date") or row.get("trade_date"))
        if tdate is None:
            rejected.append(
                RejectedRow(
                    i,
                    "missing_trade_date",
                    str(row.get("transaction_date") or row.get("trade_date") or ""),
                )
            )
            continue

        ddate = _parse_date(row.get("disclosure_date") or row.get("filed_date"))
        if ddate is None:
            rejected.append(
                RejectedRow(
                    i,
                    "missing_disclosure_date",
                    str(row.get("disclosure_date") or row.get("filed_date") or ""),
                )
            )
            continue

        if ddate < tdate:
            rejected.append(
                RejectedRow(i, "disclosure_before_trade", f"{ddate.isoformat()} < {tdate.isoformat()}")
            )
            continue

        side = _side(row.get("type") or row.get("transaction_type") or row.get("side"))
        if side is None:
            rejected.append(
                RejectedRow(
                    i,
                    "unknown_side",
                    str(row.get("type") or row.get("transaction_type") or row.get("side") or ""),
                )
            )
            continue

        amount_raw = row.get("amount")
        if amount_raw is None:
            amount_raw = row.get("range")
        parsed = try_parse_amount_band(None if amount_raw is None else str(amount_raw))
        if parsed is None:
            rejected.append(RejectedRow(i, "amount_unparsed", str(amount_raw or "")))
            continue
        lo, hi = parsed

        pid_key = _politician_id(
            row.get("representative") or row.get("senator") or row.get("name"),
            i,
        )
        accepted.append(
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

    dmin, dmax = _disclosure_bounds(accepted)
    report = IngestReport(
        source=source,
        n_read=len(rows),
        n_accepted=len(accepted),
        n_rejected=len(rejected),
        rejected=rejected,
        disclosure_min=dmin,
        disclosure_max=dmax,
    )
    return accepted, report


def load_watcher_json(path: Path, source: str) -> list[TradeEvent]:
    trades, _report = ingest_watcher_json(path, source)
    return trades


def load_prices_csv(path: Path | str) -> dict[tuple[str, date], float]:
    out: dict[tuple[str, date], float] = {}
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            normalized = {
                (k or "").strip().lower(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            }
            ticker = (normalized.get("ticker") or "").upper()
            raw_date = normalized.get("date") or ""
            raw_px = normalized.get("adj_close")
            if not ticker or not raw_date or raw_px in (None, ""):
                continue
            out[(ticker, date.fromisoformat(raw_date[:10]))] = float(raw_px)
    return out


def load_politicians_json(path: Path | str) -> list[Politician]:
    rows = _json_rows(Path(path), "politicians", "data")
    out: list[Politician] = []
    for row in rows:
        cids = row.get("committee_ids") or []
        out.append(
            Politician(
                politician_id=str(row["politician_id"]),
                name=str(row["name"]),
                chamber=str(row["chamber"]).lower(),
                party=str(row.get("party") or ""),
                state=str(row.get("state") or ""),
                seniority_years=float(row.get("seniority_years") or 0),
                committee_ids=tuple(str(cid) for cid in cids),
            )
        )
    return out


def load_securities_json(path: Path | str) -> list[Security]:
    rows = _json_rows(Path(path), "securities", "data")
    return [
        Security(
            ticker=str(row["ticker"]).strip().upper(),
            name=str(row["name"]),
            sector=str(row["sector"]),
            industry=str(row["industry"]),
            avg_dollar_volume=float(row["avg_dollar_volume"]),
        )
        for row in rows
    ]


def load_committees_json(path: Path | str) -> list[Committee]:
    rows = _json_rows(Path(path), "committees", "data")
    return [
        Committee(
            committee_id=str(row["committee_id"]),
            name=str(row["name"]),
            chamber=str(row["chamber"]).lower(),
            primary_sector=str(row.get("primary_sector") or ""),
        )
        for row in rows
    ]


def _stub_politician(politician_id: str, source: str) -> Politician:
    chamber = "senate" if "senate" in source.lower() else "house"
    return Politician(
        politician_id=politician_id,
        name=_name_from_id(politician_id),
        chamber=chamber,
        party="",
        state="",
        seniority_years=0,
    )


def apply_ingest(
    db_path: Path | str,
    *,
    trades_path: Path | str,
    prices_path: Path | str,
    source: str,
    politicians_path: Path | str | None = None,
    securities_path: Path | str | None = None,
    committees_path: Path | str | None = None,
    reset: bool = True,
) -> IngestReport:
    db_path = Path(db_path)
    if reset:
        con = reset_db(db_path)
    else:
        con = connect(db_path)
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='trades'"
        ).fetchone()
        if exists is None:
            init_db(con)

    try:
        politicians = load_politicians_json(politicians_path) if politicians_path else []
        committees = load_committees_json(committees_path) if committees_path else []
        securities = load_securities_json(securities_path) if securities_path else []

        if committees:
            upsert_committees(con, committees)
        if politicians:
            upsert_politicians(con, politicians)
        if securities:
            upsert_securities(con, securities)

        trades, report = ingest_watcher_json(trades_path, source)

        known_tickers = set(fetch_securities(con))
        known_tickers.update(s.ticker for s in securities)

        kept: list[TradeEvent] = []
        unmapped: list[str] = []
        seen_unmapped: set[str] = set()
        extra_rejected: list[RejectedRow] = []
        for trade in trades:
            if trade.ticker in known_tickers:
                kept.append(trade)
                continue
            if trade.ticker not in seen_unmapped:
                seen_unmapped.add(trade.ticker)
                unmapped.append(trade.ticker)
            extra_rejected.append(
                RejectedRow(
                    index=_trade_index(trade.trade_id, source),
                    reason="unmapped_ticker",
                    detail=trade.ticker,
                )
            )

        upserted_ids = {p.politician_id for p in politicians}
        known_pids = {p.politician_id for p in fetch_politicians(con)}
        stubs: list[Politician] = []
        stubbed: set[str] = set()
        for trade in kept:
            if trade.politician_id in known_pids or trade.politician_id in stubbed:
                continue
            stubs.append(_stub_politician(trade.politician_id, source))
            stubbed.add(trade.politician_id)
            known_pids.add(trade.politician_id)
        if stubs:
            upsert_politicians(con, stubs)
            upserted_ids.update(stubbed)

        if kept:
            insert_trades(con, kept)
        prices = load_prices_csv(prices_path)
        if prices:
            insert_prices(con, prices)

        dmin, dmax = _disclosure_bounds(kept)
        report.n_accepted = len(kept)
        report.n_rejected = report.n_rejected + len(extra_rejected)
        report.rejected.extend(extra_rejected)
        report.politicians_upserted = len(upserted_ids)
        report.securities_unmapped = unmapped
        report.disclosure_min = dmin
        report.disclosure_max = dmax
        return report
    finally:
        con.close()
