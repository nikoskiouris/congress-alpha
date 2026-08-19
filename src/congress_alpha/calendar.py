from __future__ import annotations

from datetime import date, timedelta


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5


def next_trading_day(d: date) -> date:
    cur = d
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def add_trading_days(d: date, n: int) -> date:
    """Move n trading days forward (n>=0) from d, landing on a trading day."""
    cur = next_trading_day(d)
    stepped = 0
    while stepped < n:
        cur += timedelta(days=1)
        if is_trading_day(cur):
            stepped += 1
    return cur


def trading_days_between(start: date, end: date) -> int:
    """Count trading days in (start, end] using calendar weekdays."""
    if end <= start:
        return 0
    n = 0
    cur = start
    while cur < end:
        cur += timedelta(days=1)
        if is_trading_day(cur):
            n += 1
    return n


def daterange_trading(start: date, end: date) -> list[date]:
    out: list[date] = []
    cur = start
    while cur <= end:
        if is_trading_day(cur):
            out.append(cur)
        cur += timedelta(days=1)
    return out
