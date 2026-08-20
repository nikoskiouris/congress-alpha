from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from congress_alpha.pipeline import DEFAULT_DASH, DEFAULT_DB, DEFAULT_INGEST_REPORT, run_demo

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
_DISCLOSURE_NOTE = "Signals may only use disclosure_date as event time."
_SYNTHETIC_INGEST = {
    "mode": "synthetic",
    "n_read": 0,
    "n_accepted": 0,
    "n_rejected": 0,
    "reasons": [],
    "note": "synthetic DGP",
}

app = FastAPI(title="Congress Alpha", version="0.1.0")


def _payload() -> dict:
    if DEFAULT_DASH.exists():
        return json.loads(DEFAULT_DASH.read_text())
    if DEFAULT_DB.exists():
        return run_demo()
    return run_demo()


@app.get("/api/health")
def health():
    out = {"ok": True, "has_dashboard": DEFAULT_DASH.exists()}
    if DEFAULT_DASH.exists():
        try:
            payload = json.loads(DEFAULT_DASH.read_text())
        except (OSError, json.JSONDecodeError):
            payload = {}
        if payload.get("mode"):
            out["mode"] = payload["mode"]
        else:
            out["mode"] = "synthetic"
    return out


@app.get("/api/ingest")
def ingest():
    path = DEFAULT_INGEST_REPORT
    if not path.exists():
        return dict(_SYNTHETIC_INGEST)
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return dict(_SYNTHETIC_INGEST)
    if not isinstance(raw, dict):
        return dict(_SYNTHETIC_INGEST)
    rejected = raw.get("rejected") or []
    counts: Counter[str] = Counter()
    if isinstance(rejected, list):
        for row in rejected:
            if isinstance(row, dict) and row.get("reason"):
                counts[str(row["reason"])] += 1
    note = raw.get("note") or _DISCLOSURE_NOTE
    return {
        "mode": "ingested",
        "n_read": int(raw.get("n_read") or 0),
        "n_accepted": int(raw.get("n_accepted") or 0),
        "n_rejected": int(raw.get("n_rejected") or 0),
        "reasons": [{"reason": reason, "n": n} for reason, n in counts.most_common()],
        "note": note,
    }


@app.get("/api/dashboard")
def dashboard():
    return _payload()


@app.get("/api/brief")
def brief():
    p = _payload()
    leakage = p.get("leakage") or (p.get("execution") or {}).get("leakage") or {}
    return {
        "mode": p.get("mode") or "synthetic",
        "ablations": p.get("ablations") or {},
        "leakage": leakage,
        "metrics": p.get("metrics") or {},
    }


@app.get("/api/signals/{ticker}")
def why(ticker: str):
    payload = _payload()
    ticker = ticker.upper()
    exp = payload.get("explanations", {}).get(ticker)
    if not exp:
        raise HTTPException(404, f"no live signal for {ticker}")
    return exp


@app.get("/api/politicians")
def politicians():
    return _payload().get("politician_weights", [])


@app.get("/api/backtest")
def backtest():
    p = _payload()
    return {"metrics": p.get("metrics"), "nav": p.get("nav"), "as_of": p.get("as_of")}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


if (FRONTEND / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")
