from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from congress_alpha import api

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_ingest_missing_file_is_synthetic(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DEFAULT_INGEST_REPORT", tmp_path / "missing.json")
    body = TestClient(api.app).get("/api/ingest").json()
    assert body["mode"] == "synthetic"
    assert body["n_read"] == 0
    assert body["n_accepted"] == 0
    assert body["n_rejected"] == 0
    assert body["reasons"] == []
    assert "synthetic" in body["note"].lower()
    assert "rejected" not in body


def test_ingest_unreadable_file_is_synthetic(tmp_path, monkeypatch):
    path = tmp_path / "ingest_report.json"
    path.write_text("{not-json")
    monkeypatch.setattr(api, "DEFAULT_INGEST_REPORT", path)
    body = TestClient(api.app).get("/api/ingest").json()
    assert body["mode"] == "synthetic"
    assert body["n_read"] == 0
    assert body["n_accepted"] == 0
    assert body["n_rejected"] == 0
    assert body["reasons"] == []


def test_ingest_fixture_counts_reasons(tmp_path, monkeypatch):
    path = tmp_path / "ingest_report.json"
    path.write_text(
        json.dumps(
            {
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
        )
    )
    monkeypatch.setattr(api, "DEFAULT_INGEST_REPORT", path)
    body = TestClient(api.app).get("/api/ingest").json()
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
    assert "live track record" not in body["note"].lower()
    assert "disclosure_date" in body["note"]


def _client_for_dash(tmp_path, monkeypatch, payload: dict) -> TestClient:
    path = tmp_path / "dashboard.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(api, "DEFAULT_DASH", path)
    return TestClient(api.app)


def test_health_brief_dashboard_require_synthetic_mode(tmp_path, monkeypatch):
    client = _client_for_dash(
        tmp_path,
        monkeypatch,
        {
            "mode": "synthetic",
            "metrics": {"cagr": 0.07, "sharpe": 0.2},
            "ablations": {"equal_skill": {"sharpe": 0.1}},
            "leakage": {"n_trades": 10, "n_with_delay": 10},
        },
    )
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["has_dashboard"] is True
    assert health["mode"] == "synthetic"
    brief = client.get("/api/brief").json()
    assert brief["mode"] == "synthetic"
    assert brief["metrics"]["cagr"] == 0.07
    assert brief["ablations"]["equal_skill"]["sharpe"] == 0.1
    assert brief["leakage"]["n_with_delay"] == 10
    dash = client.get("/api/dashboard").json()
    assert dash["mode"] == "synthetic"
    assert dash["metrics"]["sharpe"] == 0.2


def test_dashboard_missing_mode_still_reports_synthetic(tmp_path, monkeypatch):
    client = _client_for_dash(
        tmp_path,
        monkeypatch,
        {
            "metrics": {"cagr": 0.01},
            "ablations": {"perm_skill": {"sharpe": -0.1}},
            "execution": {"leakage": {"n_trades": 3}},
        },
    )
    assert client.get("/api/health").json()["mode"] == "synthetic"
    brief = client.get("/api/brief").json()
    assert brief["mode"] == "synthetic"
    assert brief["metrics"] == {"cagr": 0.01}
    assert brief["ablations"] == {"perm_skill": {"sharpe": -0.1}}
    assert brief["leakage"] == {"n_trades": 3}
    assert brief["mode"] != "live"


def test_ingested_mode_is_research_file_not_live(tmp_path, monkeypatch):
    client = _client_for_dash(
        tmp_path,
        monkeypatch,
        {"mode": "ingested", "metrics": {"cagr": 0.02}, "ablations": {}},
    )
    assert client.get("/api/health").json()["mode"] == "ingested"
    brief = client.get("/api/brief").json()
    assert brief["mode"] == "ingested"
    assert brief["mode"] != "live"
    assert brief["metrics"] == {"cagr": 0.02}
    blob = json.dumps(brief).lower()
    assert "live track record" not in blob
    assert client.get("/api/dashboard").json()["mode"] == "ingested"


def test_banner_copy_unchanged():
    html = FRONTEND.read_text()
    assert "RESEARCH FILE — DISCLOSURE CLOCK" in html
    assert "SYNTHETIC DEMO — NOT A LIVE TRACK RECORD" in html
    assert 'mode === "ingested"' in html
    assert "/api/ingest" in html
    assert "INGEST" in html
    assert "synthetic — no filings" in html


def test_why_panel_exposes_premove_pct(tmp_path, monkeypatch):
    client = _client_for_dash(
        tmp_path,
        monkeypatch,
        {
            "mode": "synthetic",
            "explanations": {
                "LMT": {
                    "ticker": "LMT",
                    "score": 71,
                    "premove_pct": 8.2,
                    "people": [{"name": "Ace", "committee": True, "weight": 0.4}],
                }
            },
        },
    )
    body = client.get("/api/signals/LMT").json()
    assert body["premove_pct"] == 8.2
    assert body["ticker"] == "LMT"
    html = FRONTEND.read_text()
    assert "premove_pct" in html
    assert "ALREADY MOVED" in html
    assert "Before the filing" in html
    assert "Filing is the event" in html
    assert "★ = relevant committee. Weights are post-disclosure skill, not name recognition." in html
