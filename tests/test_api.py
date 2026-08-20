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


def test_banner_copy_unchanged():
    html = FRONTEND.read_text()
    assert "RESEARCH FILE — DISCLOSURE CLOCK" in html
    assert "SYNTHETIC DEMO — NOT A LIVE TRACK RECORD" in html
    assert 'mode === "ingested"' in html
    assert "/api/ingest" in html
    assert "INGEST" in html
    assert "synthetic — no filings" in html
