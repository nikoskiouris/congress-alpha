from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from congress_alpha import api
from congress_alpha.cli import main
from congress_alpha.pipeline import run_fixture_dump

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
ROOT = Path(__file__).resolve().parents[1]


def _block_network(monkeypatch) -> None:
    import urllib.request

    def blocked(*_args, **_kwargs):
        raise OSError("network blocked: CA-011 uses recorded fixtures only")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)


def test_research_file_lights_ingested_dashboard(tmp_path, monkeypatch):
    _block_network(monkeypatch)
    dash = tmp_path / "dashboard.json"
    brief = tmp_path / "research_brief.md"
    report = tmp_path / "ingest_report.json"
    payload = run_fixture_dump(
        db_path=tmp_path / "fx.db",
        dash_path=dash,
        brief_path=brief,
        ingest_report_path=report,
    )
    assert payload["mode"] == "ingested"
    assert json.loads(dash.read_text())["mode"] == "ingested"
    assert "not a live track record" in payload["disclaimer"].lower()
    assert payload["disclaimer"].lower().count("not a live track record") >= 1
    assert report.exists()
    assert "INGESTED RESEARCH FILE" in brief.read_text()
    assert "trade_date never" in brief.read_text()

    monkeypatch.setattr(api, "DEFAULT_DASH", dash)
    monkeypatch.setattr(api, "DEFAULT_INGEST_REPORT", report)
    client = TestClient(api.app)
    body = client.get("/api/dashboard").json()
    assert body["mode"] == "ingested"
    assert body["mode"] != "synthetic"
    assert "not a live track record" in (body.get("disclaimer") or "").lower()
    assert client.get("/api/health").json()["mode"] == "ingested"
    ingest = client.get("/api/ingest").json()
    assert ingest["mode"] == "ingested"
    assert ingest["n_read"] > 0
    assert ingest["n_accepted"] > 0

    html = FRONTEND.read_text()
    assert "RESEARCH FILE — DISCLOSURE CLOCK" in html
    assert 'mode === "ingested"' in html
    banner = (
        "RESEARCH FILE — DISCLOSURE CLOCK"
        if body["mode"] == "ingested"
        else "SYNTHETIC DEMO — NOT A LIVE TRACK RECORD"
    )
    assert banner == "RESEARCH FILE — DISCLOSURE CLOCK"
    assert "place trade" not in html.lower()
    blob = json.dumps(body).lower()
    assert "broker" not in blob


def test_cli_research_file_writes_ingested_dash(tmp_path, monkeypatch):
    _block_network(monkeypatch)
    dash = tmp_path / "dashboard.json"
    rc = main(
        [
            "research-file",
            "--db",
            str(tmp_path / "fx.db"),
            "--dash",
            str(dash),
            "--brief",
            str(tmp_path / "brief.md"),
            "--ingest-report",
            str(tmp_path / "ingest_report.json"),
        ]
    )
    assert rc == 0
    assert json.loads(dash.read_text())["mode"] == "ingested"


def test_research_file_command_is_documented():
    makefile = (ROOT / "Makefile").read_text()
    assert "research-file:" in makefile
    assert "congress_alpha research-file" in makefile
    readme = (ROOT / "README.md").read_text()
    assert "make research-file" in readme
    assert "mode=ingested" in readme
    assert "not a live track record" in readme.lower()
    assert "no House/Senate scrape" in readme
