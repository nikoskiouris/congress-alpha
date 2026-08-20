from __future__ import annotations

import json

from congress_alpha.brief import write_brief
from congress_alpha.cli import main


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


def test_write_brief_contains_required_phrases(tmp_path):
    path = write_brief(_payload(), tmp_path / "research_brief.md")
    text = path.read_text()
    assert "DISCLOSURE" in text
    assert "SYNTHETIC" in text
    assert "trade_date never" in text
    assert "conviction" in text
    assert "CONGRESS ALPHA — RESEARCH BRIEF" in text
    n = text.count("\n") + (0 if text.endswith("\n") else 1)
    assert 80 <= n <= 150


def test_write_brief_ingested_classification(tmp_path):
    payload = _payload()
    payload["mode"] = "ingested"
    text = write_brief(payload, tmp_path / "brief.md").read_text()
    assert "INGESTED RESEARCH FILE" in text
    assert "THESE NUMBERS ARE NOT A LIVE TRACK RECORD" in text


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
