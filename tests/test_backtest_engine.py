from datetime import date, timedelta

import pytest

from congress_alpha.backtest import cheat_backtest_on_trade_date, run_backtest
from congress_alpha.calendar import add_trading_days, daterange_trading
from congress_alpha.costs import CostModel
from congress_alpha.event_study import run_event_study
from congress_alpha.prices import PriceStore
from congress_alpha.types import Committee, Politician, Security, TradeEvent


def test_no_later_than_blocks_forward_fill():
    start = date(2023, 6, 12)  # Monday
    end = date(2023, 6, 16)  # Friday
    px = {}
    # only Friday has a print
    px[("LMT", date(2023, 6, 16))] = 120.0
    px[("SPY", date(2023, 6, 16))] = 100.0
    store = PriceStore(px)
    wed = date(2023, 6, 14)
    assert store.get("LMT", wed) == 120.0  # forward fill allowed
    assert store.get("LMT", wed, no_later_than=wed) is None  # not past the mark


def test_costs_positive_on_open():
    secs = {"LMT": Security("LMT", "L", "Defense", "x", 1e9)}
    c, traded = CostModel().trade_cost_fraction({}, {"LMT": 0.10}, secs)
    assert traded == pytest.approx(0.10)
    assert c > 0
    zero = CostModel(commission_bps=0, half_spread_bps=0, impact_k=0)
    c0, _ = zero.trade_cost_fraction({}, {"LMT": 0.10}, secs)
    assert c0 == 0.0


def test_event_study_uses_skill_from_before_disclosure():
    start = date(2023, 1, 2)
    end = date(2023, 12, 29)
    disc = date(2023, 6, 15)
    # After disclosure LMT drifts up vs SPY.
    px = {}
    spy = 100.0
    lmt = 100.0
    for dt in daterange_trading(start, end):
        spy *= 1.0001
        if dt >= add_trading_days(disc, 1):
            lmt *= 1.004
        else:
            lmt *= 1.0001
        px[("SPY", dt)] = spy
        px[("LMT", dt)] = lmt
    store = PriceStore(px)
    trade = TradeEvent("1", "ace", "LMT", date(2023, 5, 1), disc, "BUY", 15001, 50000)
    # Skill snapshot AFTER the filing must not classify this trade as skilled.
    late_only = [(date(2023, 9, 1), {"ace": 0.9})]
    es_late = run_event_study([trade], store, late_only, date(2023, 12, 1))
    assert "skilled" not in es_late.by_skill or es_late.by_skill["skilled"][20].n == 0
    # Snapshot BEFORE the filing may classify it.
    early = [(date(2023, 3, 1), {"ace": 0.9})]
    es_early = run_event_study([trade], store, early, date(2023, 12, 1))
    assert es_early.by_skill["skilled"][20].n == 1
    assert es_early.by_horizon[20].mean > 0


def test_cheat_still_refused():
    with pytest.raises(RuntimeError, match="trade_date"):
        cheat_backtest_on_trade_date()


def test_next_session_fill_misses_overnight_pop():
    """Buy Thursday close, so Wednesday close → Thursday close is not yours."""
    start = date(2023, 1, 2)
    end = date(2024, 6, 28)
    sessions = daterange_trading(start, end)
    politicians = [
        Politician("ace", "Ace", "house", "D", "VA", 10, ("hasc",)),
        Politician("bob", "Bob", "house", "D", "VA", 8, ("hasc",)),
    ]
    committees = {"hasc": Committee("hasc", "Armed Services", "house", "Defense")}
    securities = {
        "LMT": Security("LMT", "Lockheed", "Defense", "A&D", 1e9),
        "RTX": Security("RTX", "RTX", "Defense", "A&D", 1e9),
        "SPY": Security("SPY", "SPY", "Market", "Index", 1e11),
    }
    # Flat market. One huge pop Wednesday 2023-09-13 close to Thursday 2023-09-14 close.
    pop_thu = date(2023, 9, 14)
    px = {}
    lmt = 100.0
    rtx = 100.0
    for dt in sessions:
        lmt *= 1.0015
        rtx *= 1.0015
        if dt == pop_thu:
            lmt *= 2.0
        px[("SPY", dt)] = 100.0
        px[("RTX", dt)] = rtx
        px[("LMT", dt)] = lmt
    store = PriceStore(px)

    # Many completed BUY disclosures so skill is positive and gates can fire.
    trades = []
    n = 0
    d0 = date(2023, 1, 10)
    while d0 < date(2023, 6, 1):
        n += 1
        trades.append(
            TradeEvent(str(n), "ace", "LMT", d0, add_trading_days(d0, 5), "BUY", 50001, 100000)
        )
        n += 1
        trades.append(
            TradeEvent(str(n), "bob", "RTX", d0, add_trading_days(d0, 5), "BUY", 50001, 100000)
        )
        d0 += timedelta(days=14)

    # Live cluster disclosed Tuesday 2023-09-12 so Wednesday signal (weekday 2) sees it.
    disc = date(2023, 9, 12)
    trades.append(TradeEvent("x1", "ace", "LMT", date(2023, 9, 1), disc, "BUY", 50001, 100000))
    trades.append(TradeEvent("x2", "bob", "LMT", date(2023, 9, 1), disc, "BUY", 50001, 100000))

    zero = CostModel(commission_bps=0, half_spread_bps=0, impact_k=0)
    lagged = run_backtest(
        trades, securities, politicians, committees, store,
        start=date(2023, 6, 1), end=date(2023, 10, 31),
        execution_lag=1, cost_model=zero,
    )
    same_day = run_backtest(
        trades, securities, politicians, committees, store,
        start=date(2023, 6, 1), end=date(2023, 10, 31),
        execution_lag=0, cost_model=zero,
    )
    # Next-session fill (Thu) must earn less of the Wed→Thu doubling than lag-0 (Wed close).
    def nav_after_pop(result):
        pts = result.strategies["momentum"].nav
        after = [p for p in pts if p.date >= pop_thu]
        assert after, "backtest produced no points after the pop"
        return after[0].nav

    assert nav_after_pop(lagged) < nav_after_pop(same_day) - 0.01


def test_costs_reduce_demo_like_nav():
    from congress_alpha.generate import generate
    from congress_alpha.prices import PriceStore as PS

    uni = generate(seed=7, start=date(2021, 1, 4), end=date(2024, 6, 28))
    store = PS(uni.prices)
    secs = {s.ticker: s for s in uni.securities}
    comm = {c.committee_id: c for c in uni.committees}
    kw = dict(
        trades=uni.trades,
        securities=secs,
        politicians=uni.politicians,
        committees=comm,
        store=store,
        start=date(2022, 6, 1),
        end=uni.end,
        execution_lag=1,
    )
    cheap = run_backtest(**kw, cost_model=CostModel(commission_bps=0, half_spread_bps=0, impact_k=0))
    dear = run_backtest(**kw, cost_model=CostModel())
    for strat in cheap.strategies:
        if not cheap.strategies[strat].nav:
            continue
        assert dear.strategies[strat].nav[-1].nav <= cheap.strategies[strat].nav[-1].nav + 1e-9
