from __future__ import annotations

from datetime import date, timedelta

import pytest

from congress_alpha.calendar import add_trading_days, daterange_trading
from congress_alpha.prices import PriceStore
from congress_alpha.types import Committee, Politician, Security, TradeEvent


def _path(start: date, n: int, r0: float, bump_at: int | None = None, bump: float = 0.0) -> dict:
    days = daterange_trading(start, start + timedelta(days=n * 2 + 40))[: n + 5]
    px, level = {}, 100.0
    out_days = []
    for i, dt in enumerate(days):
        if bump_at is not None and i == bump_at:
            level *= 1.0 + bump
        else:
            level *= 1.0 + r0
        px[dt] = level
        out_days.append(dt)
    return px, out_days


@pytest.fixture
def toy():
    start = date(2023, 1, 2)
    sessions = daterange_trading(start, date(2024, 6, 28))
    politicians = [
        Politician("ace", "Ace Skilled", "house", "D", "VA", 10, ("hasc",)),
        Politician("noise", "Noisy Nora", "house", "R", "AZ", 2, ()),
        Politician("lag", "Late Les", "senate", "D", "FL", 6, ("hasc",)),
    ]
    committees = {"hasc": Committee("hasc", "Armed Services", "house", "Defense")}
    securities = {
        "LMT": Security("LMT", "Lockheed", "Defense", "A&D", 1e9),
        "AAPL": Security("AAPL", "Apple", "Technology", "Hardware", 1e10),
        "SPY": Security("SPY", "SPY", "Market", "Index", 1e11),
    }
    prices: dict[tuple[str, date], float] = {}
    spy = 100.0
    lmt = 100.0
    aapl = 100.0
    # LMT drifts up after a known disclosure date.
    disc = date(2023, 6, 15)
    for dt in sessions:
        spy *= 1.0002
        aapl *= 1.00025
        if dt >= disc:
            lmt *= 1.0022  # strong post-disclosure drift
        else:
            lmt *= 1.0002
        prices[("SPY", dt)] = spy
        prices[("LMT", dt)] = lmt
        prices[("AAPL", dt)] = aapl

    trades = [
        TradeEvent("1", "ace", "LMT", date(2023, 5, 20), disc, "BUY", 15001, 50000),
        TradeEvent(
            "2",
            "ace",
            "LMT",
            date(2023, 8, 1),
            date(2023, 8, 12),
            "BUY",
            50001,
            100000,
        ),
        TradeEvent(
            "3",
            "noise",
            "AAPL",
            date(2023, 5, 2),
            date(2023, 6, 1),
            "BUY",
            1001,
            15000,
        ),
        TradeEvent(
            "4",
            "lag",
            "LMT",
            date(2023, 4, 1),
            date(2023, 5, 20),
            "BUY",
            15001,
            50000,
        ),
        # Future disclosure — must be invisible on 2023-09-01
        TradeEvent(
            "5",
            "ace",
            "LMT",
            date(2023, 9, 10),
            date(2023, 10, 5),
            "BUY",
            15001,
            50000,
        ),
    ]
    return {
        "politicians": politicians,
        "committees": committees,
        "securities": securities,
        "trades": trades,
        "store": PriceStore(prices),
        "disc": disc,
    }
