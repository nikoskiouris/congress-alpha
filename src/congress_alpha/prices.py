from __future__ import annotations

from datetime import date

import numpy as np

from congress_alpha.calendar import next_trading_day


class PriceStore:
    """Adj-close lookup with next-session fill. Never interpolates backwards."""

    def __init__(self, prices: dict[tuple[str, date], float]):
        self._px = prices
        by_ticker: dict[str, list[date]] = {}
        for ticker, dt in prices:
            by_ticker.setdefault(ticker, []).append(dt)
        self._dates = {t: sorted(ds) for t, ds in by_ticker.items()}

    def get(self, ticker: str, dt: date) -> float | None:
        key = (ticker, dt)
        if key in self._px:
            return self._px[key]
        dates = self._dates.get(ticker)
        if not dates:
            return None
        # next available session on or after dt
        lo, hi = 0, len(dates)
        while lo < hi:
            mid = (lo + hi) // 2
            if dates[mid] < dt:
                lo = mid + 1
            else:
                hi = mid
        if lo >= len(dates):
            return None
        return self._px[(ticker, dates[lo])]

    def return_between(self, ticker: str, start: date, end: date) -> float | None:
        a = self.get(ticker, next_trading_day(start))
        b = self.get(ticker, next_trading_day(end))
        if a is None or b is None or a <= 0:
            return None
        return b / a - 1.0

    def excess_return(self, ticker: str, start: date, end: date, benchmark: str = "SPY") -> float | None:
        r = self.return_between(ticker, start, end)
        m = self.return_between(benchmark, start, end)
        if r is None or m is None:
            return None
        return r - m

    def log_return_matrix(self, tickers: list[str], dates: list[date]) -> np.ndarray:
        """rows=dates, cols=tickers, daily simple returns. Missing -> 0."""
        out = np.zeros((len(dates), len(tickers)))
        for j, tkr in enumerate(tickers):
            prev = None
            for i, dt in enumerate(dates):
                px = self.get(tkr, dt)
                if px is None:
                    continue
                if prev is not None and prev > 0:
                    out[i, j] = px / prev - 1.0
                prev = px
        return out
