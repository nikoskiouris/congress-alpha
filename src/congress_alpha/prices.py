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
        self.last_date: date | None = None
        if prices:
            self.last_date = max(dt for _, dt in prices)

    def get(
        self,
        ticker: str,
        dt: date,
        no_later_than: date | None = None,
    ) -> float | None:
        key = (ticker, dt)
        if key in self._px:
            if no_later_than is not None and dt > no_later_than:
                return None
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
        found = dates[lo]
        if no_later_than is not None and found > no_later_than:
            return None
        return self._px[(ticker, found)]

    def return_between(self, ticker: str, start: date, end: date) -> float | None:
        a = self.get(ticker, next_trading_day(start), no_later_than=end)
        b = self.get(ticker, next_trading_day(end), no_later_than=end)
        if a is None or b is None or a <= 0:
            return None
        return b / a - 1.0

    def holding_return(
        self,
        ticker: str,
        start: date,
        end: date,
        *,
        no_later_than: date | None = None,
    ) -> float | None:
        """Close-to-close. Missing prints do not fill past `no_later_than`."""
        cap = no_later_than if no_later_than is not None else end
        a = self.get(ticker, start, no_later_than=cap)
        b = self.get(ticker, end, no_later_than=cap)
        if a is None or b is None or a <= 0:
            return None
        return b / a - 1.0

    def excess_return(
        self,
        ticker: str,
        start: date,
        end: date,
        benchmark: str = "SPY",
        *,
        no_later_than: date | None = None,
    ) -> float | None:
        r = self.holding_return(ticker, start, end, no_later_than=no_later_than)
        m = self.holding_return(benchmark, start, end, no_later_than=no_later_than)
        if r is None or m is None:
            return None
        return r - m

    def log_return_matrix(self, tickers: list[str], dates: list[date]) -> np.ndarray:
        """rows=dates, cols=tickers, daily simple returns. Missing -> 0."""
        out = np.zeros((len(dates), len(tickers)))
        for j, tkr in enumerate(tickers):
            prev = None
            for i, dt in enumerate(dates):
                px = self.get(tkr, dt, no_later_than=dt)
                if px is None:
                    continue
                if prev is not None and prev > 0:
                    out[i, j] = px / prev - 1.0
                prev = px
        return out
