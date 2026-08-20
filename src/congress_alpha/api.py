from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from congress_alpha.pipeline import DEFAULT_DASH, DEFAULT_DB, run_demo

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

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
