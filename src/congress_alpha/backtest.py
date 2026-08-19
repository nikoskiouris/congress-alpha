"""Walk-forward event-time backtester.

At each signal date t (default Wednesday):
  1. Fit politician weights using only trades whose evaluation window closed before t.
  2. Build signals from trades with disclosure_date <= t.
  3. Fill the book at t + execution_lag sessions (default next close).
  4. Realize close-to-close returns on the previous fill, then pay costs of the new trade.

This is the entire product. If it only works when you cheat and use trade_date,
the idea does not have tradable alpha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from congress_alpha.calendar import add_trading_days, daterange_trading
from congress_alpha.config import (
    BENCHMARK,
    COST_SWEEP_BPS,
    EXECUTION_LAG_SESSIONS,
    STRATEGIES,
)
from congress_alpha.costs import CostModel, flat_cost_fraction
from congress_alpha.event_study import EventStudy, event_study_public, run_event_study
from congress_alpha.metrics import Performance, evaluate
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
class _Period:
    exec_date: date
    signal_date: date
    gross: float
    spy: float
    cost: float
    traded: float
    n_holdings: int
    invested: float
    cash: float


@dataclass
class StrategyResult:
    strategy: str
    nav: list[BacktestPoint]
    last_portfolio: Portfolio | None
    last_book: object
    stats: Performance
    cost_sweep: dict[str, dict] = field(default_factory=dict)

    @property
    def cagr(self) -> float:
        return self.stats.cagr

    @property
    def excess_cagr(self) -> float:
        return self.stats.excess_cagr

    @property
    def vol(self) -> float:
        return self.stats.vol

    @property
    def sharpe(self) -> float:
        return self.stats.sharpe

    @property
    def max_dd(self) -> float:
        return self.stats.max_dd

    @property
    def hit_weeks(self) -> float:
        return self.stats.hit_rate

    @property
    def avg_holdings(self) -> float:
        return self.stats.avg_holdings

    @property
    def turnover(self) -> float:
        return self.stats.turnover


@dataclass
class BacktestResult:
    strategies: dict[str, StrategyResult]
    spy: list[BacktestPoint]
    last_as_of: date
    snapshots: dict = field(default_factory=dict)
    event_study: EventStudy | None = None
    skill_path: list[tuple[date, dict[str, float]]] = field(default_factory=list)
    execution_lag: int = EXECUTION_LAG_SESSIONS
    cost_model: str = ""
    leakage: dict = field(default_factory=dict)


def leakage_audit(trades: list[TradeEvent], last_as_of: date) -> dict:
    delayed = [t for t in trades if t.trade_date < t.disclosure_date]
    traps = [t for t in delayed if t.trade_date <= last_as_of < t.disclosure_date]
    future = [t for t in trades if t.disclosure_date > last_as_of]
    return {
        "n_trades": len(trades),
        "n_with_reporting_delay": len(delayed),
        "n_trade_date_traps_at_last_as_of": len(traps),
        "n_disclosures_after_last_as_of": len(future),
        "note": (
            "trade_date traps are filings the public has not seen yet. "
            "Using them as event time is look-ahead. This engine never does."
        ),
    }


def _asset_return(
    holdings: dict[str, float],
    store: PriceStore,
    start: date,
    end: date,
) -> float:
    r = 0.0
    for tkr, w in holdings.items():
        pr = store.holding_return(tkr, start, end, no_later_than=end)
        if pr is not None:
            r += w * pr
    return r


def _replay(
    periods: list[_Period],
    *,
    entry_cost: float,
    entry_traded: float,
    one_way_bps: float | None,
) -> tuple[np.ndarray, np.ndarray, list[date], list[float], np.ndarray]:
    """Rebuild net returns. If one_way_bps is set, replace model costs with a flat sweep."""
    n = len(periods)
    if n == 0:
        return np.array([]), np.array([]), [], [], np.array([])
    gross = np.array([p.gross for p in periods], dtype=float)
    spy = np.array([p.spy for p in periods], dtype=float)
    dates = [p.exec_date for p in periods]
    if one_way_bps is None:
        costs = np.array([p.cost for p in periods], dtype=float)
        haircut = entry_cost
    else:
        costs = np.array(
            [flat_cost_fraction(p.traded, one_way_bps) for p in periods], dtype=float
        )
        haircut = flat_cost_fraction(entry_traded, one_way_bps)
    hold = (1.0 + gross) * (1.0 - costs)
    hold[0] *= 1.0 - haircut
    net = hold - 1.0
    nav = np.cumprod(hold)
    return net, spy, dates, costs.tolist(), nav


def _points(
    strategy: str,
    periods: list[_Period],
    net: np.ndarray,
    costs: list[float],
    nav: np.ndarray,
) -> list[BacktestPoint]:
    out = []
    for i, p in enumerate(periods):
        spy_r = p.spy
        out.append(
            BacktestPoint(
                date=p.exec_date,
                strategy=strategy,
                nav=float(nav[i]),
                daily_return=float(net[i]),
                excess_return=float(net[i] - spy_r),
                n_holdings=p.n_holdings,
                invested=p.invested,
                gross_return=p.gross,
                cost=float(costs[i]),
                turnover=0.5 * p.traded,
                cash=p.cash,
                signal_date=p.signal_date,
            )
        )
    return out


def _sweep(
    periods: list[_Period],
    entry_traded: float,
    avg_holdings: float,
    avg_invested: float,
    avg_turnover: float,
    n_trials: int,
) -> dict[str, dict]:
    out = {}
    for bps in COST_SWEEP_BPS:
        net, spy, dates, _, _ = _replay(
            periods,
            entry_cost=0.0,
            entry_traded=entry_traded,
            one_way_bps=bps,
        )
        stats = evaluate(
            net,
            spy,
            dates,
            avg_holdings=avg_holdings,
            avg_invested=avg_invested,
            turnover=avg_turnover,
            n_trials=n_trials,
        )
        key = str(int(bps)) if bps == int(bps) else str(bps)
        out[key] = {
            "bps": bps,
            "cagr": round(stats.cagr, 4),
            "sharpe": round(stats.sharpe, 3),
            "max_dd": round(stats.max_dd, 4),
            "excess_cagr": round(stats.excess_cagr, 4),
        }
    return out


def _finish_strategy(
    name: str,
    periods: list[_Period],
    entry_cost: float,
    entry_traded: float,
    last_port: Portfolio | None,
    last_book,
    n_trials: int,
) -> tuple[StrategyResult, list[BacktestPoint]]:
    if len(periods) < 2:
        empty = Performance()
        return (
            StrategyResult(name, [], last_port, last_book, empty, {}),
            [],
        )
    avg_h = float(sum(p.n_holdings for p in periods) / len(periods))
    avg_inv = float(sum(p.invested for p in periods) / len(periods))
    avg_to = float(sum(0.5 * p.traded for p in periods) / len(periods))
    net, spy, dates, costs, nav = _replay(
        periods,
        entry_cost=entry_cost,
        entry_traded=entry_traded,
        one_way_bps=None,
    )
    stats = evaluate(
        net,
        spy,
        dates,
        avg_holdings=avg_h,
        avg_invested=avg_inv,
        turnover=avg_to,
        avg_cost=float(np.mean(costs)) if len(costs) else 0.0,
        n_trials=n_trials,
    )
    pts = _points(name, periods, net, costs, nav)
    if pts:
        pts[0].cost += entry_cost
    sweep = _sweep(periods, entry_traded, avg_h, avg_inv, avg_to, n_trials)
    return StrategyResult(name, pts, last_port, last_book, stats, sweep), pts


def run_backtest(
    trades: list[TradeEvent],
    securities: dict[str, Security],
    politicians: list[Politician],
    committees: dict[str, Committee],
    store: PriceStore,
    start: date,
    end: date,
    rebalance_weekday: int = 2,
    execution_lag: int = EXECUTION_LAG_SESSIONS,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    cost_model = cost_model or CostModel()
    sessions = daterange_trading(start, end)
    if not sessions:
        raise ValueError("no trading days in window")

    first_disc = min(t.disclosure_date for t in trades) if trades else start
    warmup = first_disc + timedelta(days=180)
    rebalance = [
        d for d in sessions if d >= warmup and d.weekday() == rebalance_weekday
    ]
    if len(rebalance) < 8:
        rebalance = [d for d in sessions if d >= warmup][::5]

    holdings: dict[str, dict[str, float]] = {s: {} for s in STRATEGIES}
    last_port: dict[str, Portfolio | None] = {s: None for s in STRATEGIES}
    last_book = None
    last_signals = None
    skill_path: list[tuple[date, dict[str, float]]] = []
    periods: dict[str, list[_Period]] = {s: [] for s in STRATEGIES}
    entry_cost = {s: 0.0 for s in STRATEGIES}
    entry_traded = {s: 0.0 for s in STRATEGIES}
    cache = precompute_trade_alphas(trades, store)

    prev_exec: date | None = None
    last_signal = rebalance[0]

    for signal_date in rebalance:
        exec_date = add_trading_days(signal_date, execution_lag)
        if store.last_date is not None and exec_date > store.last_date:
            break

        book = fit_skill(
            signal_date, trades, securities, store, politicians, cache=cache
        )
        last_book = book
        skill_path.append((signal_date, dict(book.overall)))
        sigs = build_signals(
            signal_date, trades, book, securities, politicians, committees, store
        )
        last_signals = sigs
        last_signal = signal_date

        new_h: dict[str, dict[str, float]] = {}
        new_cash: dict[str, float] = {}
        for strat in STRATEGIES:
            port = construct(signal_date, strat, sigs.get(strat, {}), securities)
            last_port[strat] = port
            new_h[strat] = port.weights
            new_cash[strat] = port.cash

        if prev_exec is None:
            for strat in STRATEGIES:
                c, traded = cost_model.trade_cost_fraction(
                    {}, new_h[strat], securities
                )
                entry_cost[strat] = c
                entry_traded[strat] = traded
            holdings = new_h
            prev_exec = exec_date
            continue

        spy_r = store.holding_return(
            BENCHMARK, prev_exec, exec_date, no_later_than=exec_date
        ) or 0.0
        for strat in STRATEGIES:
            gross = _asset_return(holdings[strat], store, prev_exec, exec_date)
            c, traded = cost_model.trade_cost_fraction(
                holdings[strat], new_h[strat], securities
            )
            invested = sum(new_h[strat].values())
            periods[strat].append(
                _Period(
                    exec_date=exec_date,
                    signal_date=signal_date,
                    gross=gross,
                    spy=spy_r,
                    cost=c,
                    traded=traded,
                    n_holdings=len(new_h[strat]),
                    invested=invested,
                    cash=new_cash[strat],
                )
            )
            holdings[strat] = new_h[strat]
        prev_exec = exec_date

    n_trials = len(STRATEGIES)
    strategies: dict[str, StrategyResult] = {}
    spy_pts: list[BacktestPoint] = []
    for strat in STRATEGIES:
        res, pts = _finish_strategy(
            strat,
            periods[strat],
            entry_cost[strat],
            entry_traded[strat],
            last_port[strat],
            last_book,
            n_trials,
        )
        strategies[strat] = res
        if not spy_pts and pts:
            spy_nav = np.cumprod(1.0 + np.array([p.spy for p in periods[strat]]))
            spy_pts = [
                BacktestPoint(
                    date=p.exec_date,
                    strategy="spy",
                    nav=float(spy_nav[i]),
                    daily_return=p.spy,
                    excess_return=0.0,
                    n_holdings=1,
                    invested=1.0,
                    gross_return=p.spy,
                    cost=0.0,
                    turnover=0.0,
                    cash=0.0,
                    signal_date=p.signal_date,
                )
                for i, p in enumerate(periods[strat])
            ]

    es = run_event_study(trades, store, skill_path, last_signal)
    return BacktestResult(
        strategies=strategies,
        spy=spy_pts,
        last_as_of=last_signal,
        snapshots={
            "book": last_book,
            "signals": last_signals,
            "portfolios": last_port,
            "event_study": event_study_public(es),
        },
        event_study=es,
        skill_path=skill_path,
        execution_lag=execution_lag,
        cost_model=(
            f"commission={cost_model.commission_bps}bps "
            f"half_spread={cost_model.half_spread_bps}bps "
            f"impact_k={cost_model.impact_k} aum={cost_model.aum:.0f} "
            f"lag={execution_lag}"
        ),
        leakage=leakage_audit(trades, last_signal),
    )


def cheat_backtest_on_trade_date(*args, **kwargs):
    """Intentionally not implemented. Using trade_date as event time is the bug."""
    raise RuntimeError("trade_date is not a valid event time")
