from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from congress_alpha.ingest import (
    apply_ingest,
    ingest_watcher_json,
    load_prices_csv,
    load_watcher_json,
    parse_amount_band,
)
from congress_alpha.warehouse import connect, fetch_politicians, fetch_prices, fetch_trades

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
DIRTY = FIXTURES / "trades_dirty.json"
OK = FIXTURES / "trades_ok.json"
SOURCE = "house-stock-watcher"


def test_parse_amount_band_still_reads_stock_act_range():
    lo, hi = parse_amount_band("$15,001 - $50,000")
    assert lo == 15001
    assert hi == 50000


def test_dirty_file_rejects_without_accepting_bad_rows():
    trades, report = ingest_watcher_json(DIRTY, SOURCE)
    assert report.n_read >= 10
    assert report.n_rejected >= 5
    assert report.n_accepted + report.n_rejected == report.n_read
    assert len(trades) == report.n_accepted

    accepted_ids = {t.trade_id for t in trades}
    for row in report.rejected:
        assert f"{SOURCE}-{row.index:06d}" not in accepted_ids

    reasons = {row.reason for row in report.rejected}
    assert "disclosure_before_trade" in reasons
    assert "missing_ticker" in reasons
    assert "options_or_complex" in reasons
    assert "missing_trade_date" in reasons
    assert "missing_disclosure_date" in reasons
    assert "unknown_side" in reasons
    assert "amount_unparsed" in reasons

    assert all(t.disclosure_date >= t.trade_date for t in trades)
    assert not any(t.disclosure_date < t.trade_date for t in trades)

    raw = json.loads(DIRTY.read_text())
    for row in report.rejected:
        if row.reason != "disclosure_before_trade":
            continue
        src = raw[row.index]
        tdate = src["transaction_date"]
        ddate = src["disclosure_date"]
        assert ddate < tdate
        assert not any(
            t.ticker == src["ticker"]
            and t.trade_date.isoformat() == tdate
            and t.disclosure_date.isoformat() == ddate
            for t in trades
        )


def test_amount_unparsed_rejected():
    trades, report = ingest_watcher_json(DIRTY, SOURCE)
    assert any(row.reason == "amount_unparsed" for row in report.rejected)
    assert all(t.amount_min > 0 and t.amount_max >= t.amount_min for t in trades)


def test_options_ticker_rejected():
    trades, report = ingest_watcher_json(DIRTY, SOURCE)
    assert any(row.reason == "options_or_complex" for row in report.rejected)
    assert any("CALL" in row.detail or "PUT" in row.detail for row in report.rejected)
    for trade in trades:
        assert "CALL" not in trade.ticker
        assert "PUT" not in trade.ticker
        assert " " not in trade.ticker
        assert "^" not in trade.ticker


def test_unmapped_ticker_rejected(tmp_path):
    db = tmp_path / "unmapped.db"
    report = apply_ingest(
        db,
        trades_path=DIRTY,
        prices_path=FIXTURES / "prices.csv",
        source=SOURCE,
        politicians_path=FIXTURES / "politicians.json",
        securities_path=FIXTURES / "securities.json",
        committees_path=FIXTURES / "committees.json",
        reset=True,
    )
    assert "ACME" in report.securities_unmapped
    assert any(row.reason == "unmapped_ticker" and row.detail == "ACME" for row in report.rejected)

    con = connect(db)
    stored = fetch_trades(con)
    con.close()
    assert all(t.ticker != "ACME" for t in stored)
    assert "ACME" not in {t.ticker for t in stored}


def test_apply_ingest_writes_sqlite_trades(tmp_path):
    db = tmp_path / "ok.db"
    report = apply_ingest(
        db,
        trades_path=OK,
        prices_path=FIXTURES / "prices.csv",
        source=SOURCE,
        politicians_path=FIXTURES / "politicians.json",
        securities_path=FIXTURES / "securities.json",
        committees_path=FIXTURES / "committees.json",
        reset=True,
    )
    assert report.n_accepted >= 4
    assert report.n_rejected == 0
    assert report.politicians_upserted >= 4
    assert report.disclosure_min is not None
    assert report.disclosure_max is not None
    assert report.disclosure_min <= report.disclosure_max

    con = connect(db)
    stored = fetch_trades(con)
    prices = fetch_prices(con)
    politicians = fetch_politicians(con)
    con.close()

    assert len(stored) == report.n_accepted
    assert stored
    assert all(t.disclosure_date >= t.trade_date for t in stored)
    assert {t.ticker for t in stored} <= {"LMT", "NVDA", "JPM"}
    assert ("SPY", date(2023, 6, 1)) in prices
    ids = {p.politician_id for p in politicians}
    assert "avery-hale" in ids
    assert "pat-exemplar" in ids  # auto-stub for missing reference row


def test_apply_ingest_dirty_never_stores_lookahead_dates(tmp_path):
    db = tmp_path / "dirty.db"
    apply_ingest(
        db,
        trades_path=DIRTY,
        prices_path=FIXTURES / "prices.csv",
        source=SOURCE,
        politicians_path=FIXTURES / "politicians.json",
        securities_path=FIXTURES / "securities.json",
        committees_path=FIXTURES / "committees.json",
        reset=True,
    )
    con = connect(db)
    stored = fetch_trades(con)
    con.close()
    assert stored
    assert all(t.disclosure_date >= t.trade_date for t in stored)


def test_prices_csv_loads():
    prices = load_prices_csv(FIXTURES / "prices.csv")
    assert len(prices) >= 40
    assert ("LMT", date(2023, 6, 1)) in prices
    assert ("NVDA", date(2023, 6, 1)) in prices
    assert ("SPY", date(2023, 6, 1)) in prices
    assert ("JPM", date(2023, 6, 1)) in prices
    assert ("SPY", date(2024, 1, 8)) in prices
    assert all(isinstance(px, float) and px > 0 for px in prices.values())


def test_spy_prices_kept_without_security_row(tmp_path):
    securities = tmp_path / "securities_no_spy.json"
    securities.write_text(
        json.dumps(
            [
                {
                    "ticker": "LMT",
                    "name": "Lockheed Martin",
                    "sector": "Defense",
                    "industry": "Aerospace & Defense",
                    "avg_dollar_volume": 8e8,
                },
                {
                    "ticker": "NVDA",
                    "name": "NVIDIA",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                    "avg_dollar_volume": 2e10,
                },
                {
                    "ticker": "JPM",
                    "name": "JPMorgan",
                    "sector": "Financials",
                    "industry": "Banks",
                    "avg_dollar_volume": 5e9,
                },
            ]
        )
    )
    db = tmp_path / "spy.db"
    apply_ingest(
        db,
        trades_path=OK,
        prices_path=FIXTURES / "prices.csv",
        source=SOURCE,
        securities_path=securities,
        reset=True,
    )
    con = connect(db)
    prices = fetch_prices(con)
    tickers = {row["ticker"] for row in con.execute("SELECT ticker FROM securities")}
    con.close()
    assert "SPY" not in tickers
    assert any(tkr == "SPY" for tkr, _dt in prices)


def test_as_public_dict_json_serializable():
    _trades, report = ingest_watcher_json(DIRTY, SOURCE)
    payload = report.as_public_dict()
    encoded = json.dumps(payload)
    loaded = json.loads(encoded)
    assert loaded["source"] == SOURCE
    assert loaded["n_read"] == report.n_read
    assert loaded["n_rejected"] == report.n_rejected
    assert loaded["note"] == "Signals may only use disclosure_date as event time."
    assert isinstance(loaded["rejected"], list)
    assert loaded["disclosure_min"] is None or isinstance(loaded["disclosure_min"], str)


def test_load_watcher_json_returns_only_trades():
    trades = load_watcher_json(OK, SOURCE)
    assert len(trades) == 6
    assert all(t.source == SOURCE for t in trades)


def test_wrapped_transactions_key(tmp_path):
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"transactions": json.loads(OK.read_text())}))
    trades, report = ingest_watcher_json(wrapped, SOURCE)
    assert report.n_accepted == 6
    assert len(trades) == 6


def test_senate_source_stubs_senate_chamber(tmp_path):
    db = tmp_path / "senate.db"
    apply_ingest(
        db,
        trades_path=OK,
        prices_path=FIXTURES / "prices.csv",
        source="senate-stock-watcher",
        securities_path=FIXTURES / "securities.json",
        reset=True,
    )
    con = connect(db)
    politicians = {p.politician_id: p for p in fetch_politicians(con)}
    con.close()
    assert politicians["pat-exemplar"].chamber == "senate"
    assert politicians["avery-hale"].chamber == "senate"
