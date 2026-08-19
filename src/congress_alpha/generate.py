"""Synthetic universe with known ground-truth skill.

Names are fictional. The DGP is the test: event-time training should recover
post-disclosure skill and ignore pre-disclosure-only "skill".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from congress_alpha.calendar import add_trading_days, daterange_trading, next_trading_day
from congress_alpha.config import AMOUNT_BANDS, BENCHMARK
from congress_alpha.types import Committee, Politician, Security, TradeEvent


@dataclass
class Universe:
    politicians: list[Politician]
    committees: list[Committee]
    securities: list[Security]
    trades: list[TradeEvent]
    prices: dict[tuple[str, date], float]
    start: date
    end: date


COMMITTEES = [
    Committee("hasc", "Armed Services", "house", "Defense"),
    Committee("hfsc", "Financial Services", "house", "Financials"),
    Committee("energy", "Energy and Commerce", "house", "Healthcare"),
    Committee("science", "Science, Space, and Technology", "house", "Technology"),
    Committee("sasc", "Armed Services", "senate", "Defense"),
    Committee("banking", "Banking, Housing, and Urban Affairs", "senate", "Financials"),
]

SECURITIES = [
    Security("LMT", "Lockheed Martin", "Defense", "Aerospace & Defense", 8e8),
    Security("RTX", "RTX", "Defense", "Aerospace & Defense", 9e8),
    Security("NOC", "Northrop Grumman", "Defense", "Aerospace & Defense", 4e8),
    Security("BA", "Boeing", "Defense", "Aerospace", 1.2e9),
    Security("NVDA", "NVIDIA", "Technology", "Semiconductors", 2e10),
    Security("MSFT", "Microsoft", "Technology", "Software", 1.5e10),
    Security("AAPL", "Apple", "Technology", "Hardware", 1.2e10),
    Security("GOOGL", "Alphabet", "Technology", "Internet", 8e9),
    Security("AMZN", "Amazon", "Consumer", "Internet Retail", 9e9),
    Security("TSLA", "Tesla", "Consumer", "Autos", 7e9),
    Security("JPM", "JPMorgan", "Financials", "Banks", 5e9),
    Security("GS", "Goldman Sachs", "Financials", "Capital Markets", 2e9),
    Security("UNH", "UnitedHealth", "Healthcare", "Managed Care", 3e9),
    Security("PFE", "Pfizer", "Healthcare", "Pharma", 2e9),
    Security("XOM", "Exxon Mobil", "Energy", "Integrated Oil", 4e9),
    Security("CAT", "Caterpillar", "Industrials", "Machinery", 2e9),
    Security(BENCHMARK, "SPDR S&P 500", "Market", "Index", 3e10),
]

# Ground-truth profiles. post_alpha is extra drift AFTER disclosure.
# pre_alpha is extra drift BETWEEN trade and disclosure (not tradable).
POLITICIANS = [
    Politician("hale", "Avery Hale", "house", "D", "VA", 14, ("hasc",)),
    Politician("ellis", "Quinn Ellis", "senate", "R", "TX", 9, ("sasc",)),
    Politician("blake", "Rowan Blake", "house", "D", "CA", 6, ("hasc", "science")),
    Politician("quinn", "Morgan Quinn", "senate", "D", "NY", 18, ("banking",)),
    Politician("ames", "Skyler Ames", "house", "D", "WA", 4, ("science",)),
    Politician("cole", "Harper Cole", "house", "R", "OH", 11, ("energy",)),
    Politician("patel", "Drew Patel", "senate", "R", "FL", 7, ("sasc",)),
    Politician("vale", "Casey Vale", "house", "D", "IL", 8, ("science",)),
    Politician("brooks", "Riley Brooks", "house", "R", "AZ", 3, ()),
    Politician("nash", "Jordan Nash", "senate", "I", "ME", 12, ()),
]

# id -> (home_sector, mean_lag, post_alpha, pre_alpha, trade_freq)
PROFILES = {
    "hale": ("Defense", 8, 0.085, 0.02, 0.55),
    "ellis": ("Defense", 9, 0.060, 0.015, 0.45),
    "blake": ("Defense", 11, 0.050, 0.02, 0.40),
    "quinn": ("Financials", 12, 0.055, 0.01, 0.40),
    "ames": ("Technology", 10, 0.045, 0.02, 0.40),
    "cole": ("Healthcare", 14, 0.040, 0.01, 0.30),
    "patel": ("Defense", 42, 0.015, 0.07, 0.35),  # slow filer: alpha mostly gone
    "vale": ("Technology", 25, 0.000, 0.12, 0.40),  # looks genius on trade date
    "brooks": ("Consumer", 20, 0.000, 0.00, 0.50),  # noise
    "nash": ("Energy", 15, -0.080, 0.00, 0.55),  # inverse, isolated sector
}

SECTOR_TICKERS = {
    "Defense": ["LMT", "RTX", "NOC", "BA"],
    "Technology": ["NVDA", "MSFT", "AAPL", "GOOGL"],
    "Financials": ["JPM", "GS"],
    "Healthcare": ["UNH", "PFE"],
    "Consumer": ["AMZN", "TSLA"],
    "Energy": ["XOM"],
    "Industrials": ["CAT"],
}


def _band(rng: np.random.Generator, conviction: str) -> tuple[float, float]:
    if conviction == "high":
        idx = int(rng.integers(3, 6))
    elif conviction == "low":
        idx = int(rng.integers(0, 2))
    else:
        idx = int(rng.integers(1, 4))
    return AMOUNT_BANDS[idx]


def generate(seed: int = 7, start: date | None = None, end: date | None = None) -> Universe:
    start = start or date(2021, 1, 4)
    end = end or date(2026, 6, 30)
    rng = np.random.default_rng(seed)
    sessions = daterange_trading(start, end)
    securities = list(SECURITIES)
    tickers = [s.ticker for s in securities if s.ticker != BENCHMARK] + [BENCHMARK]

    # --- prices: market + sector + idio. Extra drift attached to specific trades later.
    n = len(sessions)
    mkt = rng.normal(0.00028, 0.0095, n)
    sector_shock = {
        sec: rng.normal(0.00005, 0.0065, n) for sec in {s.sector for s in securities}
    }
    px: dict[tuple[str, date], float] = {}
    levels: dict[str, np.ndarray] = {}
    for sec in securities:
        beta = 1.0 if sec.ticker == BENCHMARK else float(rng.uniform(0.7, 1.3))
        idio = rng.normal(0.0, 0.012 if sec.ticker != BENCHMARK else 0.0, n)
        shock = np.zeros(n) if sec.ticker == BENCHMARK else sector_shock[sec.sector]
        rets = 0.00015 + beta * mkt + shock + idio
        lvl = 100.0 * np.exp(np.cumsum(rets))
        levels[sec.ticker] = lvl
        for i, dt in enumerate(sessions):
            px[(sec.ticker, dt)] = float(lvl[i])

    session_index = {dt: i for i, dt in enumerate(sessions)}

    def bump(ticker: str, from_dt: date, days: int, total_extra: float) -> None:
        """Add a total log-drift over `days` trading sessions starting at from_dt."""
        if abs(total_extra) < 1e-9:
            return
        i0 = session_index.get(next_trading_day(from_dt))
        if i0 is None:
            return
        i1 = min(len(sessions) - 1, i0 + max(days, 1))
        span = max(i1 - i0, 1)
        per = total_extra / span
        lvl = levels[ticker]
        # apply multiplicative drift to the path from i0 onward
        factor = 1.0
        for i in range(i0, len(sessions)):
            if i < i1:
                factor *= np.exp(per)
            levels[ticker][i] = lvl[i] * factor
            px[(ticker, sessions[i])] = float(levels[ticker][i])
        # keep levels array in sync
        levels[ticker] = np.array([px[(ticker, d)] for d in sessions])

    trades: list[TradeEvent] = []
    trade_n = 0
    first_trade = next_trading_day(start + timedelta(days=365))

    def new_trade(pid, ticker, tdate, lag, side, conv) -> TradeEvent:
        nonlocal trade_n
        trade_n += 1
        lo, hi = _band(rng, conv)
        ddate = add_trading_days(tdate, int(max(lag, 1)))
        owner = "self" if rng.random() > 0.18 else "spouse"
        return TradeEvent(
            trade_id=f"t{trade_n:05d}",
            politician_id=pid,
            ticker=ticker,
            trade_date=tdate,
            disclosure_date=ddate,
            side=side,
            amount_min=lo,
            amount_max=hi,
            owner=owner,
            source="synthetic",
        )

    # Regular flow of trades
    for dt in sessions:
        if dt < first_trade or dt > end - timedelta(days=80):
            continue
        if dt.weekday() != 1:  # mostly batch on Tuesdays
            if rng.random() > 0.08:
                continue
        for p in POLITICIANS:
            home, mean_lag, post_a, pre_a, freq = PROFILES[p.politician_id]
            if rng.random() > freq * 0.12:
                continue
            in_home = rng.random() < 0.72
            if p.politician_id == "nash":
                in_home = True
            if in_home:
                ticker = str(rng.choice(SECTOR_TICKERS[home]))
            else:
                other = [t for t in tickers if t != BENCHMARK]
                ticker = str(rng.choice(other))
            lag = int(max(3, rng.normal(mean_lag, 4)))
            lag = int(np.clip(lag, 3, 55))
            side = "BUY" if rng.random() > 0.22 else "SELL"
            conv = "high" if rng.random() < 0.25 else ("low" if rng.random() < 0.3 else "mid")
            tr = new_trade(p.politician_id, ticker, dt, lag, side, conv)
            trades.append(tr)
            sign = 1.0 if side == "BUY" else -1.0
            # Only apply ground-truth drift in home sector; other-sector trades are noise.
            if in_home:
                bump(ticker, tr.trade_date, max(tr.lag_days, 1), sign * pre_a * (0.6 + 0.8 * rng.random()))
                bump(ticker, tr.disclosure_date, 40, sign * post_a * (0.6 + 0.8 * rng.random()))

    # Inject a few explicit consensus clusters in defense (the product demo).
    cluster_days = [
        date(2023, 3, 7),
        date(2024, 1, 16),
        date(2024, 9, 10),
        date(2025, 4, 8),
        date(2025, 11, 18),
        date(2026, 2, 10),
        date(2026, 4, 14),
        date(2026, 5, 12),
        date(2026, 6, 2),
    ]
    for cdt in cluster_days:
        cdt = next_trading_day(cdt)
        if cdt < first_trade or cdt > end - timedelta(days=20):
            continue
        ticker = str(rng.choice(["LMT", "RTX", "NOC"]))
        for cluster_pid in ("hale", "ellis", "blake"):
            lag = int(PROFILES[cluster_pid][1] + rng.integers(-2, 3))
            tr = new_trade(cluster_pid, ticker, cdt, lag, "BUY", "high")
            trades.append(tr)
            bump(ticker, tr.trade_date, max(tr.lag_days, 1), 0.02)
            bump(ticker, tr.disclosure_date, 45, 0.09)

    # A couple of live non-defense clusters so the last as-of isn't empty.
    extra = [
        (date(2026, 5, 19), "NVDA", ("ames", "blake", "vale")),
        (date(2026, 6, 3), "JPM", ("quinn", "hale", "ellis")),
        (date(2026, 6, 9), "LMT", ("hale", "ellis", "blake")),
    ]
    for cdt, ticker, pids in extra:
        cdt = next_trading_day(cdt)
        if cdt > end - timedelta(days=12):
            continue
        for cluster_pid in pids:
            lag = int(max(6, PROFILES[cluster_pid][1] - 2))
            tr = new_trade(cluster_pid, ticker, cdt, lag, "BUY", "high")
            trades.append(tr)
            bump(ticker, tr.disclosure_date, 30, 0.06)

    trades.sort(key=lambda t: (t.disclosure_date, t.trade_id))
    return Universe(
        politicians=list(POLITICIANS),
        committees=list(COMMITTEES),
        securities=securities,
        trades=trades,
        prices=px,
        start=start,
        end=end,
    )
