"""Build warehouse, run walk-forward, persist snapshots for the API."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from congress_alpha.backtest import BacktestResult, run_backtest
from congress_alpha.explain import congress_score, explain_ticker
from congress_alpha.generate import generate
from congress_alpha.prices import PriceStore
from congress_alpha.skill import SkillBook
from congress_alpha.warehouse import (
    fetch_committees,
    fetch_politicians,
    fetch_prices,
    fetch_securities,
    fetch_trades,
    insert_prices,
    insert_trades,
    load_reference,
    replace_json_table,
    reset_db,
)

DEFAULT_DB = Path("data/congress_alpha.db")
DEFAULT_DASH = Path("data/dashboard.json")


def persist_universe(db_path: Path, seed: int = 7):
    uni = generate(seed=seed)
    con = reset_db(db_path)
    load_reference(con, uni.politicians, uni.committees, uni.securities)
    insert_trades(con, uni.trades)
    insert_prices(con, uni.prices)
    con.close()
    return uni


def persist_backtest(db_path: Path, result: BacktestResult, securities, politicians) -> None:
    import sqlite3

    con = sqlite3.connect(str(db_path))
    book: SkillBook = result.snapshots["book"]
    as_of = result.last_as_of.isoformat()
    skill_rows = []
    for row in book.rows:
        skill_rows.append(
            {
                "as_of": as_of,
                "politician_id": row.politician_id,
                "sector": row.sector,
                "horizon": row.horizon,
                "alpha": row.alpha,
                "hit_rate": row.hit_rate,
                "n": row.n,
                "weight": row.weight,
            }
        )
    if skill_rows:
        replace_json_table(con, "skill_snapshots", skill_rows)
    delay_rows = [
        {
            "as_of": as_of,
            "lag_bucket": k,
            "remaining_alpha": v,
            "n": 0,
        }
        for k, v in book.delay_remaining.items()
    ]
    replace_json_table(con, "delay_snapshots", delay_rows)

    sig_rows = []
    port_rows = []
    signals = result.snapshots["signals"] or {}
    ports = result.snapshots["portfolios"] or {}
    for strat, by_tkr in signals.items():
        for tkr, sig in by_tkr.items():
            sig_rows.append(
                {
                    "as_of": as_of,
                    "ticker": tkr,
                    "strategy": strat,
                    "signal": sig.raw_signal,
                    "n_politicians": sig.n_politicians,
                    "n_predictive": sig.n_predictive,
                    "n_relevant_committee": sig.n_relevant_committee,
                    "avg_lag_days": sig.avg_lag_days,
                    "components_json": json.dumps(
                        [
                            {
                                "pid": f.trade.politician_id,
                                "side": f.trade.side,
                                "c": round(f.contribution, 4),
                            }
                            for f in sig.features[:12]
                        ]
                    ),
                }
            )
    for strat, port in ports.items():
        if port is None:
            continue
        for tkr, w in port.weights.items():
            sig = port.signals.get(tkr)
            port_rows.append(
                {
                    "as_of": as_of,
                    "strategy": strat,
                    "ticker": tkr,
                    "weight": w,
                    "signal": sig.raw_signal if sig else 0.0,
                }
            )
        if port.cash > 1e-6:
            port_rows.append(
                {
                    "as_of": as_of,
                    "strategy": strat,
                    "ticker": "CASH",
                    "weight": port.cash,
                    "signal": 0.0,
                }
            )
    if sig_rows:
        replace_json_table(con, "signals", sig_rows)
    if port_rows:
        replace_json_table(con, "portfolios", port_rows)

    nav_rows = []
    for strat, res in result.strategies.items():
        for p in res.nav:
            nav_rows.append(
                {
                    "date": p.date.isoformat(),
                    "strategy": strat,
                    "nav": p.nav,
                    "daily_return": p.daily_return,
                    "excess_return": p.excess_return,
                    "n_holdings": p.n_holdings,
                    "invested": p.invested,
                    "gross_return": p.gross_return,
                    "cost": p.cost,
                    "turnover": p.turnover,
                    "cash": p.cash,
                }
            )
    for p in result.spy:
        nav_rows.append(
            {
                "date": p.date.isoformat(),
                "strategy": "spy",
                "nav": p.nav,
                "daily_return": p.daily_return,
                "excess_return": 0.0,
                "n_holdings": 1,
                "invested": 1.0,
                "gross_return": p.gross_return,
                "cost": 0.0,
                "turnover": 0.0,
                "cash": 0.0,
            }
        )
    if nav_rows:
        replace_json_table(con, "backtest_nav", nav_rows)
    con.close()


def dashboard_payload(result: BacktestResult, securities, politicians, store: PriceStore) -> dict:
    as_of: date = result.last_as_of
    book: SkillBook = result.snapshots["book"]
    all_signals = result.snapshots["signals"]
    # Headline score uses momentum (full disclosed flow). Books stay separate.
    signals = all_signals.get("momentum") or {}
    score, label = congress_score(signals)
    ranked = sorted(signals.values(), key=lambda s: s.raw_signal, reverse=True)
    ranked = [s for s in ranked if s.n_politicians >= 2 or abs(s.raw_signal) >= 0.2]
    top = []
    for sig in ranked[:8]:
        if sig.ticker not in securities:
            continue
        top.append(
            {
                "ticker": sig.ticker,
                "name": securities[sig.ticker].name,
                "sector": sig.sector,
                "signal": round(sig.raw_signal, 3),
                "score": int(round(100 / (1 + __import__("math").exp(-sig.raw_signal)))),
                "n_politicians": sig.n_politicians,
                "n_predictive": sig.n_predictive,
            }
        )
    ports = {}
    for strat, port in (result.snapshots["portfolios"] or {}).items():
        if port is None:
            continue
        ports[strat] = [
            {
                "ticker": tkr,
                "weight": round(w, 4),
                "sector": securities[tkr].sector if tkr in securities else "Cash",
            }
            for tkr, w in sorted(port.weights.items(), key=lambda kv: -kv[1])
        ]
        if port.cash > 0.01:
            ports[strat].append({"ticker": "CASH", "weight": round(port.cash, 4), "sector": "Cash"})

    explanations = {}
    for sig in ranked[:12]:
        explanations[sig.ticker] = explain_ticker(
            sig, securities, politicians, book, store, as_of
        )

    weights_table = []
    for pid, w in sorted(book.overall.items(), key=lambda kv: -kv[1]):
        name = next((p.name for p in politicians if p.politician_id == pid), pid)
        defense = book.sector.get((pid, "Defense"))
        tech = book.sector.get((pid, "Technology"))
        hc = book.sector.get((pid, "Healthcare"))
        weights_table.append(
            {
                "id": pid,
                "name": name,
                "overall": round(w, 3),
                "defense": None if defense is None else round(defense, 3),
                "tech": None if tech is None else round(tech, 3),
                "healthcare": None if hc is None else round(hc, 3),
                "n": round(book.sample_n.get(pid, 0.0), 1),
                "alpha20": round(book.overall_alpha.get(pid, 0.0), 4),
                "hit_rate": round(book.hit_rate.get(pid, 0.5), 3),
            }
        )

    def series(strat: str):
        pts = result.spy if strat == "spy" else result.strategies[strat].nav
        return [{"date": p.date.isoformat(), "nav": round(p.nav, 4)} for p in pts]

    def pack_metrics(res) -> dict:
        s = res.stats
        def r(x, n=4):
            if x is None:
                return None
            try:
                if x != x:  # nan
                    return None
            except Exception:
                return None
            return round(float(x), n)

        return {
            "cagr": r(s.cagr),
            "excess_cagr": r(s.excess_cagr),
            "vol": r(s.vol),
            "sharpe": r(s.sharpe, 3),
            "max_dd": r(s.max_dd),
            "hit_weeks": r(s.hit_rate, 3),
            "avg_holdings": r(s.avg_holdings, 2),
            "turnover": r(s.turnover, 3),
            "sortino": r(s.sortino, 3),
            "calmar": r(s.calmar, 3),
            "information_ratio": r(s.information_ratio, 3),
            "tstat_excess": r(s.tstat_excess, 2),
            "pvalue_excess": r(s.pvalue_excess, 4),
            "beta": r(s.beta, 3),
            "alpha_ann": r(s.alpha_ann),
            "deflated_sharpe": r(s.deflated_sharpe, 3),
            "sharpe_ci": [r(s.sharpe_ci_low, 2), r(s.sharpe_ci_high, 2)],
            "avg_invested": r(s.avg_invested, 3),
            "turnover_ann": r(s.turnover_ann, 3),
            "avg_cost": r(s.avg_cost, 5),
            "max_dd_days": s.max_dd_days,
            "var_5": r(s.var_5),
            "cvar_5": r(s.cvar_5),
            "skew": r(s.skew, 3),
            "kurtosis": r(s.kurtosis, 3),
            "yearly": {k: round(v, 4) for k, v in s.yearly.items()},
            "cost_sweep": res.cost_sweep,
        }

    metrics = {strat: pack_metrics(res) for strat, res in result.strategies.items()}
    if result.spy:
        import numpy as np

        from congress_alpha.metrics import evaluate

        rets = np.array([p.daily_return for p in result.spy], dtype=float)
        dates = [p.date for p in result.spy]
        spy_stats = evaluate(rets, np.zeros_like(rets), dates, avg_holdings=1, avg_invested=1.0)
        dummy = type("S", (), {"stats": spy_stats, "cost_sweep": {}})()
        metrics["spy"] = pack_metrics(dummy)
        metrics["spy"]["excess_cagr"] = 0.0
        metrics["spy"]["information_ratio"] = 0.0

    return {
        "as_of": as_of.isoformat(),
        "score": score,
        "label": label,
        "top_signals": top,
        "portfolios": ports,
        "explanations": explanations,
        "politician_weights": weights_table,
        "delay_decay": {k: round(v, 3) for k, v in book.delay_remaining.items()},
        "nav": {s: series(s) for s in list(result.strategies) + ["spy"]},
        "metrics": metrics,
        "event_study": result.snapshots.get("event_study") or {},
        "execution": {
            "lag_sessions": result.execution_lag,
            "cost_model": result.cost_model,
            "leakage": result.leakage,
        },
        "disclaimer": (
            "Synthetic demonstration. Not investment advice. "
            "Signals are computed from disclosure_date, never trade_date. "
            "Backtest fills next session after the signal date and pays spread/impact costs."
        ),
    }


def run_demo(db_path: Path = DEFAULT_DB, dash_path: Path = DEFAULT_DASH, seed: int = 7) -> dict:
    uni = persist_universe(db_path, seed=seed)
    store = PriceStore(uni.prices)
    securities = {s.ticker: s for s in uni.securities}
    committees = {c.committee_id: c for c in uni.committees}
    # Start research window after prices exist.
    bt_start = date(2022, 6, 1)
    result = run_backtest(
        uni.trades,
        securities,
        uni.politicians,
        committees,
        store,
        start=bt_start,
        end=uni.end,
    )
    persist_backtest(db_path, result, securities, uni.politicians)
    payload = dashboard_payload(result, securities, uni.politicians, store)
    dash_path.parent.mkdir(parents=True, exist_ok=True)
    dash_path.write_text(json.dumps(payload, indent=2))
    return payload


def load_from_db(db_path: Path = DEFAULT_DB):
    import sqlite3

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    politicians = fetch_politicians(con)
    committees = fetch_committees(con)
    securities = fetch_securities(con)
    trades = fetch_trades(con)
    prices = fetch_prices(con)
    con.close()
    return politicians, committees, securities, trades, PriceStore(prices)
