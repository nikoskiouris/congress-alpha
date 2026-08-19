"""Walk-forward event-time backtester.

At each rebalance date t:
  1. Fit politician weights using only trades whose evaluation window closed before t.
  2. Build signals from trades with disclosure_date <= t.
  3. Form the portfolio. Next-session returns are applied after t is known.

This is the entire product. If it only works when you cheat and use trade_date,
the idea does not have tradable alpha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from congress_alpha.calendar import daterange_trading
from congress_alpha.config import BENCHMARK, STRATEGIES
from congress_alpha.portfolio import construct
from congress_alpha.prices import PriceStore
from congress_alpha.signal import build_signals
from congress_alpha.skill import fit_skill, precompute_trade_alphas
from congress_alpha.types import (
    BacktestPoint,
    Committee,
    Politician,
    Portfolio,
    Security,
    TradeEvent,
)


@dataclass
class StrategyResult:
    strategy: str
    nav: list[BacktestPoint]
    last_portfolio: Portfolio | None
    last_book: object
    cagr: float
    excess_cagr: float
    vol: float
    sharpe: float
    max_dd: float
    hit_weeks: float
    avg_holdings: float
    turnover: float


@dataclass
class BacktestResult:
    strategies: dict[str, StrategyResult]
    spy: list[BacktestPoint]
    last_as_of: date
    snapshots: dict = field(default_factory=dict)


def run_backtest(
    trades: list[TradeEvent],
    securities: dict[str, Security],
    politicians: list[Politician],
    committees: dict[str, Committee],
    store: PriceStore,
    start: date,
    end: date,
    rebalance_weekday: int = 2,
) -> BacktestResult:
    sessions = daterange_trading(start, end)
    if not sessions:
        raise ValueError("no trading days in window")

    # Warmup: need completed 120d windows after first disclosures.
    first_disc = min(t.disclosure_date for t in trades) if trades else start
    warmup = first_disc + timedelta(days=180)
    rebalance = [
        d
        for d in sessions
        if d >= warmup and d.weekday() == rebalance_weekday
    ]
    if len(rebalance) < 8:
        rebalance = [d for d in sessions if d >= warmup][::5]

    holdings: dict[str, dict[str, float]] = {s: {} for s in STRATEGIES}
    nav = {s: 1.0 for s in STRATEGIES}
    spy_nav = 1.0
    history: dict[str, list[BacktestPoint]] = {s: [] for s in STRATEGIES}
    spy_hist: list[BacktestPoint] = []
    last_port: dict[str, Portfolio | None] = {s: None for s in STRATEGIES}
    last_book = None
    last_signals = None
    turn_acc = {s: 0.0 for s in STRATEGIES}
    turn_n = {s: 0 for s in STRATEGIES}

    cache = precompute_trade_alphas(trades, store)
    prev = rebalance[0]
    for i, as_of in enumerate(rebalance):
        # Realize returns from prev -> as_of on the *previous* weights.
        if i > 0:
            for strat in STRATEGIES:
                r = 0.0
                for tkr, w in holdings[strat].items():
                    px0 = store.get(tkr, prev)
                    px1 = store.get(tkr, as_of)
                    if px0 and px1:
                        r += w * (px1 / px0 - 1.0)
                # cash earns 0
                spy0 = store.get(BENCHMARK, prev)
                spy1 = store.get(BENCHMARK, as_of)
                spy_r = (spy1 / spy0 - 1.0) if spy0 and spy1 else 0.0
                nav[strat] *= 1.0 + r
                history[strat].append(
                    BacktestPoint(
                        date=as_of,
                        strategy=strat,
                        nav=nav[strat],
                        daily_return=r,
                        excess_return=r - spy_r,
                        n_holdings=len(holdings[strat]),
                        invested=sum(holdings[strat].values()),
                    )
                )
            spy0 = store.get(BENCHMARK, prev)
            spy1 = store.get(BENCHMARK, as_of)
            spy_r = (spy1 / spy0 - 1.0) if spy0 and spy1 else 0.0
            spy_nav *= 1.0 + spy_r
            spy_hist.append(
                BacktestPoint(
                    date=as_of,
                    strategy="spy",
                    nav=spy_nav,
                    daily_return=spy_r,
                    excess_return=0.0,
                    n_holdings=1,
                    invested=1.0,
                )
            )

        book = fit_skill(
            as_of, trades, securities, store, politicians, cache=cache
        )
        last_book = book
        sigs = build_signals(
            as_of, trades, book, securities, politicians, committees, store
        )
        last_signals = sigs
        for strat in STRATEGIES:
            port = construct(as_of, strat, sigs.get(strat, {}), securities)
            last_port[strat] = port
            old = holdings[strat]
            new = port.weights
            names = set(old) | set(new)
            if names:
                turn_acc[strat] += 0.5 * sum(
                    abs(new.get(t, 0.0) - old.get(t, 0.0)) for t in names
                )
                turn_n[strat] += 1
            holdings[strat] = new
        prev = as_of

    years = max((rebalance[-1] - rebalance[0]).days / 365.25, 1e-6)
    strategies: dict[str, StrategyResult] = {}
    import numpy as np

    for strat in STRATEGIES:
        pts = history[strat]
        if len(pts) < 2:
            strategies[strat] = StrategyResult(
                strat, pts, last_port[strat], last_book, 0, 0, 0, 0, 0, 0, 0, 0
            )
            continue
        rets = np.array([p.daily_return for p in pts])
        xs = np.array([p.excess_return for p in pts])
        nav0, nav1 = 1.0, pts[-1].nav
        cagr = (nav1 / nav0) ** (1.0 / years) - 1.0
        vol = float(rets.std(ddof=1) * (52 ** 0.5)) if len(rets) > 2 else 0.0
        excess_cagr = float(xs.mean()) * 52
        sharpe = excess_cagr / vol if vol > 1e-9 else 0.0
        peak, max_dd = 1.0, 0.0
        eq = 1.0
        for p in pts:
            eq = p.nav
            peak = max(peak, eq)
            max_dd = min(max_dd, eq / peak - 1.0)
        hit = float((xs > 0).mean())
        avg_h = float(sum(p.n_holdings for p in pts) / len(pts))
        to = turn_acc[strat] / max(turn_n[strat], 1)
        strategies[strat] = StrategyResult(
            strategy=strat,
            nav=pts,
            last_portfolio=last_port[strat],
            last_book=last_book,
            cagr=cagr,
            excess_cagr=excess_cagr,
            vol=vol,
            sharpe=sharpe,
            max_dd=max_dd,
            hit_weeks=hit,
            avg_holdings=avg_h,
            turnover=to,
        )

    return BacktestResult(
        strategies=strategies,
        spy=spy_hist,
        last_as_of=rebalance[-1],
        snapshots={
            "book": last_book,
            "signals": last_signals,
            "portfolios": last_port,
        },
    )


def cheat_backtest_on_trade_date(*args, **kwargs):
    """Intentionally not implemented. Using trade_date as event time is the bug."""
    raise RuntimeError("trade_date is not a valid event time")
