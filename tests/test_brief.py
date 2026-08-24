from __future__ import annotations

import json

from congress_alpha.brief import write_brief
from congress_alpha.cli import main
from congress_alpha.pipeline import (
    ingest_summary_from_report,
    synthetic_ingest_summary,
)


def _payload() -> dict:
    return {
        "mode": "synthetic",
        "as_of": "2024-06-26",
        "metrics": {
            "conviction": {
                "cagr": 0.12,
                "excess_cagr": 0.03,
                "sharpe": 0.85,
                "tstat_excess": 1.40,
                "max_dd": -0.11,
                "deflated_sharpe": 0.42,
                "hit_weeks": 0.55,
            },
            "consensus": {
                "cagr": 0.08,
                "excess_cagr": 0.01,
                "sharpe": 0.50,
                "tstat_excess": 0.80,
                "max_dd": -0.09,
                "deflated_sharpe": 0.20,
            },
            "momentum": {
                "cagr": 0.10,
                "excess_cagr": 0.02,
                "sharpe": 0.70,
                "tstat_excess": 1.10,
                "max_dd": -0.14,
                "deflated_sharpe": 0.31,
            },
            "spy": {
                "cagr": 0.09,
                "excess_cagr": 0.0,
                "sharpe": 0.60,
                "tstat_excess": 0.0,
                "max_dd": -0.20,
                "deflated_sharpe": 0.25,
            },
        },
        "ablations": {
            "equal_skill": {
                "strategy": "conviction",
                "cagr": 0.10,
                "excess_cagr": 0.01,
                "sharpe": 0.72,
                "tstat_excess": 1.05,
                "max_dd": -0.12,
                "note": "flat politician weights",
            },
            "no_delay_decay": {
                "strategy": "conviction",
                "cagr": 0.13,
                "excess_cagr": 0.04,
                "sharpe": 0.90,
                "tstat_excess": 1.50,
                "max_dd": -0.11,
                "note": "delay decay off",
            },
            "placebo_skill": {
                "strategy": "conviction",
                "cagr": 0.04,
                "excess_cagr": -0.02,
                "sharpe": 0.20,
                "tstat_excess": 0.30,
                "max_dd": -0.18,
                "note": "shuffled skill",
            },
        },
        "leakage": {
            "n_trades": 40,
            "n_with_reporting_delay": 38,
            "n_trade_date_traps_at_last_as_of": 1,
            "n_disclosures_after_last_as_of": 2,
            "note": "trade_date traps are filings the public has not seen yet.",
        },
        "event_study": {
            "by_horizon": {"20": {"n": 12, "mean": 0.021, "tstat": 1.8, "hit": 0.58}},
            "by_skill": {"skilled": {"20": {"n": 5, "mean": 0.04, "tstat": 2.1, "hit": 0.80}}},
        },
        "execution": {
            "lag_sessions": 1,
            "cost_model": "commission=1.0bps half_spread=4.0bps impact_k=5.0 aum=10000000 lag=1",
        },
        "disclaimer": "Synthetic demonstration. Not investment advice.",
    }


def _ingest_report_payload() -> dict:
    return {
        "n_read": 10,
        "n_accepted": 6,
        "n_rejected": 4,
        "rejected": [
            {"index": 0, "reason": "missing_ticker", "detail": ""},
            {"index": 1, "reason": "missing_ticker", "detail": ""},
            {"index": 2, "reason": "amount_unparsed", "detail": ""},
            {"index": 3, "reason": "options_or_complex", "detail": ""},
        ],
        "note": "Signals may only use disclosure_date as event time.",
        "disclosure_min": "2020-01-01",
        "disclosure_max": "2024-12-31",
    }


def test_write_brief_contains_required_phrases(tmp_path):
    path = write_brief(_payload(), tmp_path / "research_brief.md")
    text = path.read_text()
    assert "DISCLOSURE" in text
    assert "SYNTHETIC" in text
    assert "trade_date never" in text
    assert "conviction" in text
    assert "CONGRESS ALPHA — RESEARCH BRIEF" in text
    assert "## DATA HYGIENE" in text
    n = text.count("\n") + (0 if text.endswith("\n") else 1)
    assert 80 <= n <= 180


def test_write_brief_ingested_classification(tmp_path):
    payload = _payload()
    payload["mode"] = "ingested"
    text = write_brief(payload, tmp_path / "brief.md").read_text()
    assert "INGESTED RESEARCH FILE" in text
    assert "THESE NUMBERS ARE NOT A LIVE TRACK RECORD" in text


def test_write_brief_data_hygiene_from_ingest(tmp_path):
    payload = _payload()
    payload["mode"] = "ingested"
    payload["ingest"] = {
        "mode": "ingested",
        "n_read": 10,
        "n_accepted": 6,
        "n_rejected": 4,
        "reasons": [
            {"reason": "missing_ticker", "n": 2},
            {"reason": "amount_unparsed", "n": 1},
            {"reason": "options_or_complex", "n": 1},
        ],
        "note": "Signals may only use disclosure_date as event time.",
    }
    text = write_brief(payload, tmp_path / "brief.md").read_text()
    assert "## DATA HYGIENE" in text
    assert "n_read: 10" in text
    assert "n_accepted: 6" in text
    assert "n_rejected: 4" in text
    assert "missing_ticker" in text
    assert "not alpha" in text.lower()
    assert "THESE NUMBERS ARE NOT A LIVE TRACK RECORD" in text
    assert "INGESTED RESEARCH FILE" in text
    assert "file hygiene" in text.lower()


def test_write_brief_defaults_missing_ingest_to_synthetic_zeros(tmp_path):
    payload = _payload()
    assert "ingest" not in payload
    text = write_brief(payload, tmp_path / "brief.md").read_text()
    assert "## DATA HYGIENE" in text
    assert "n_read: 0" in text
    assert "synthetic" in text.lower()
    assert "THESE NUMBERS ARE NOT A LIVE TRACK RECORD" in text
    assert "not alpha" in text.lower()
    assert "SYNTHETIC DEMO" in text


def test_synthetic_ingest_summary_shape():
    body = synthetic_ingest_summary()
    assert body["mode"] == "synthetic"
    assert body["n_read"] == 0
    assert body["n_accepted"] == 0
    assert body["n_rejected"] == 0
    assert body["reasons"] == []
    assert "rejected" not in body
    note = body["note"].lower()
    assert "synthetic" in note
    assert "not a live" in note
    assert "not alpha" in note


def test_ingest_summary_from_report_counts_reasons(tmp_path):
    path = tmp_path / "ingest_report.json"
    path.write_text(json.dumps(_ingest_report_payload()))
    body = ingest_summary_from_report(path)
    assert body["mode"] == "ingested"
    assert body["n_read"] == 10
    assert body["n_accepted"] == 6
    assert body["n_rejected"] == 4
    assert body["reasons"][0] == {"reason": "missing_ticker", "n": 2}
    assert {row["reason"]: row["n"] for row in body["reasons"]} == {
        "missing_ticker": 2,
        "amount_unparsed": 1,
        "options_or_complex": 1,
    }
    assert "rejected" not in body
    assert "disclosure_min" not in body
    assert "disclosure_max" not in body


def test_ingest_summary_missing_is_synthetic(tmp_path):
    body = ingest_summary_from_report(tmp_path / "missing.json")
    assert body["mode"] == "synthetic"
    assert body["n_read"] == 0
    assert body["n_accepted"] == 0
    assert body["n_rejected"] == 0
    assert body["reasons"] == []


def test_ingest_summary_missing_ingested_hygiene_unknown(tmp_path):
    body = ingest_summary_from_report(tmp_path / "missing.json", on_missing="ingested")
    assert body["mode"] == "ingested"
    assert body["n_read"] == 0
    assert body["n_accepted"] == 0
    assert body["n_rejected"] == 0
    assert body["reasons"] == []
    note = body["note"].lower()
    assert "missing" in note or "hygiene unknown" in note
    assert "not alpha" in note


def test_cli_brief_command(tmp_path):
    dash = tmp_path / "dashboard.json"
    out = tmp_path / "research_brief.md"
    dash.write_text(json.dumps(_payload()))
    rc = main(["brief", "--dash", str(dash), "--out", str(out)])
    assert rc == 0
    text = out.read_text()
    assert "DISCLOSURE" in text
    assert "SYNTHETIC" in text
    assert "trade_date never" in text
    assert "conviction" in text
    assert "## DATA HYGIENE" in text


def test_run_from_db_on_fixtures(tmp_path):
    from datetime import date
    from pathlib import Path

    from congress_alpha.ingest import apply_ingest
    from congress_alpha.pipeline import run_from_db

    repo = Path(__file__).resolve().parents[1] / "data" / "fixtures"
    db = tmp_path / "fx.db"
    apply_ingest(
        db,
        trades_path=repo / "trades_ok.json",
        prices_path=repo / "prices.csv",
        source="house-stock-watcher",
        politicians_path=repo / "politicians.json",
        securities_path=repo / "securities.json",
        committees_path=repo / "committees.json",
        reset=True,
    )
    report_path = tmp_path / "ingest_report.json"
    report_path.write_text(json.dumps(_ingest_report_payload()))
    payload = run_from_db(
        db_path=db,
        dash_path=tmp_path / "dash.json",
        brief_path=tmp_path / "brief.md",
        run_ablations=True,
        start=date(2023, 6, 1),
        ingest_report_path=report_path,
    )
    assert payload["mode"] == "ingested"
    assert "disclosure_date" in payload["disclaimer"]
    ingest = payload["ingest"]
    assert ingest["mode"] == "ingested"
    assert ingest["n_read"] == 10
    assert ingest["n_accepted"] == 6
    assert ingest["n_rejected"] == 4
    assert ingest["reasons"][0] == {"reason": "missing_ticker", "n": 2}
    assert "rejected" not in ingest
    assert (tmp_path / "brief.md").exists()
    text = (tmp_path / "brief.md").read_text()
    assert "INGESTED RESEARCH FILE" in text
    assert "trade_date never" in text
    assert "## DATA HYGIENE" in text
    assert "n_accepted: 6" in text
    assert "n_rejected: 4" in text
    assert "missing_ticker" in text
    assert "not alpha" in text.lower()


def test_run_from_db_rejects_empty_warehouse(tmp_path):
    from congress_alpha.pipeline import run_from_db
    from congress_alpha.warehouse import reset_db

    db = tmp_path / "empty.db"
    con = reset_db(db)
    con.close()
    try:
        run_from_db(
            db_path=db,
            dash_path=tmp_path / "dash.json",
            brief_path=tmp_path / "brief.md",
        )
        raise AssertionError("empty warehouse should fail")
    except ValueError as exc:
        msg = str(exc).lower()
        assert "trade" in msg or "price" in msg
