"""Plain-text walk-forward report."""

from __future__ import annotations

from congress_alpha.backtest import BacktestResult
from congress_alpha.event_study import EventStudy
from congress_alpha.metrics import Performance


def _pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "   n/a"
    return f"{x * 100:.{digits}f}%"


def _f(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "  n/a"
    return f"{x:.{digits}f}"


def _stats_row(name: str, s: Performance) -> str:
    return (
        f"{name:12} {_pct(s.cagr):>8} {_pct(s.excess_cagr):>8} {_f(s.sharpe):>7} "
        f"{_f(s.information_ratio):>7} {_f(s.tstat_excess):>7} {_pct(s.max_dd):>8} "
        f"{_f(s.deflated_sharpe):>6}"
    )


def _event_table(es: EventStudy) -> str:
    lines = ["EVENT STUDY  post-disclosure CAR vs SPY, next session, PIT skill"]
    header = f"{'bucket':16} " + " ".join(f"{h:>14}d" for h in es.by_horizon)
    lines.append(header)
    def row(name: str, cells: dict) -> str:
        bits = [f"{name:16}"]
        for h in es.by_horizon:
            c = cells.get(h)
            if c is None or c.n == 0:
                bits.append(f"{'—':>14}")
            else:
                bits.append(f"{c.mean:+.2%} t={c.tstat:4.1f}".rjust(14))
        return " ".join(bits)
    lines.append(row("all", es.by_horizon))
    for name, cells in es.by_skill.items():
        lines.append(row(name, cells))
    for name, cells in es.by_lag.items():
        lines.append(row(f"lag {name}", cells))
    lines.append(es.note)
    return "\n".join(lines)


def format_report(result: BacktestResult) -> str:
    lines = [
        "CONGRESS ALPHA  walk-forward",
        f"as_of {result.last_as_of}  {result.cost_model}",
        "",
        f"{'strategy':12} {'cagr':>8} {'excess':>8} {'sharpe':>7} {'IR':>7} {'t':>7} {'maxdd':>8} {'DSR':>6}",
    ]
    for name, res in result.strategies.items():
        lines.append(_stats_row(name, res.stats))
    if result.spy:
        from congress_alpha.metrics import evaluate
        import numpy as np

        rets = np.array([p.daily_return for p in result.spy])
        dates = [p.date for p in result.spy]
        spy_stats = evaluate(rets, np.zeros_like(rets), dates)
        spy_stats.excess_cagr = 0.0
        spy_stats.information_ratio = 0.0
        spy_stats.tstat_excess = 0.0
        lines.append(_stats_row("spy", spy_stats))
    lines.append("")
    if result.strategies:
        any_res = next(iter(result.strategies.values()))
        lines.append("YEARLY CAGR-like close-to-close")
        years = sorted({y for r in result.strategies.values() for y in r.stats.yearly})
        hdr = f"{'year':8} " + " ".join(f"{s:>12}" for s in result.strategies) 
        lines.append(hdr)
        for y in years:
            row = f"{y:8}"
            for s, res in result.strategies.items():
                row += f" {_pct(res.stats.yearly.get(y, 0.0)):>12}"
            lines.append(row)
        lines.append("")
        lines.append("COST SWEEP  Sharpe by one-way bps (gross path, flat cost)")
        hdr = f"{'bps':8} " + " ".join(f"{s:>12}" for s in result.strategies)
        lines.append(hdr)
        keys = list(any_res.cost_sweep)
        for k in keys:
            row = f"{k+'bp':8}"
            for res in result.strategies.values():
                sh = res.cost_sweep.get(k, {}).get("sharpe", 0.0)
                row += f" {_f(sh):>12}"
            lines.append(row)
        lines.append("")
    if result.event_study is not None:
        lines.append(_event_table(result.event_study))
        lines.append("")
    if result.leakage:
        lines.append(
            "LOOK-AHEAD TRAPS AVOIDED  "
            f"{result.leakage.get('n_with_reporting_delay', 0)} delayed filings, "
            f"{result.leakage.get('n_trade_date_traps_at_last_as_of', 0)} still private at last as_of"
        )
        lines.append(result.leakage.get("note", ""))
    return "\n".join(lines)
