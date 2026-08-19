"""Point-in-time post-disclosure event study.

Skill assigned to a trade is the last walk-forward weight with as_of < disclosure_date.
Never the politician's full-sample skill. That would be look-ahead.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import numpy as np

from congress_alpha.calendar import add_trading_days
from congress_alpha.config import (
    BENCHMARK,
    CONVICTION_MIN_WEIGHT,
    HORIZONS,
    LABEL_ENTRY_LAG_SESSIONS,
)
from congress_alpha.prices import PriceStore
from congress_alpha.skill import lag_bucket
from congress_alpha.types import TradeEvent


@dataclass
class EventCell:
    n: int
    mean: float
    tstat: float
    hit: float


@dataclass
class EventStudy:
    by_horizon: dict[int, EventCell]
    by_skill: dict[str, dict[int, EventCell]]
    by_lag: dict[str, dict[int, EventCell]]
    note: str = (
        "CARs are next-session post-disclosure excess vs SPY. "
        "Skill buckets use the last weight known strictly before disclosure_date."
    )


def _cell(vals: list[float]) -> EventCell:
    if not vals:
        return EventCell(0, 0.0, 0.0, 0.0)
    x = np.asarray(vals, dtype=float)
    n = len(x)
    mu = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 2 else 0.0
    t = (mu / (sd / math_sqrt(n))) if sd > 1e-18 else 0.0
    hit = float((x > 0).mean())
    return EventCell(n, mu, t, hit)


def math_sqrt(n: int) -> float:
    return float(n) ** 0.5


def _skill_before(
    path: list[tuple[date, dict[str, float]]], disclosure: date
) -> dict[str, float]:
    w: dict[str, float] = {}
    for as_of, overall in path:
        if as_of < disclosure:
            w = overall
        else:
            break
    return w


def _bucket_skill(weight: float) -> str:
    if weight >= CONVICTION_MIN_WEIGHT:
        return "skilled"
    if weight <= 0.0:
        return "unskilled"
    return "mid"


def run_event_study(
    trades: list[TradeEvent],
    store: PriceStore,
    skill_path: list[tuple[date, dict[str, float]]],
    last_as_of: date,
    entry_lag: int = LABEL_ENTRY_LAG_SESSIONS,
) -> EventStudy:
    skill_path = sorted(skill_path, key=lambda x: x[0])
    by_h: dict[int, list[float]] = {h: [] for h in HORIZONS}
    by_skill: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_lag: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    cap = store.last_date or last_as_of
    for tr in trades:
        if tr.disclosure_date >= last_as_of:
            continue
        weights = _skill_before(skill_path, tr.disclosure_date)
        skill_name = _bucket_skill(weights.get(tr.politician_id, 0.0))
        lb = lag_bucket(tr.lag_days)
        entry = add_trading_days(tr.disclosure_date, entry_lag)
        for h in HORIZONS:
            end = add_trading_days(entry, h)
            if end >= cap:
                continue
            xs = store.excess_return(
                tr.ticker, entry, end, BENCHMARK, no_later_than=end
            )
            if xs is None:
                continue
            car = tr.direction * xs
            by_h[h].append(car)
            by_skill[skill_name][h].append(car)
            by_lag[lb][h].append(car)

    return EventStudy(
        by_horizon={h: _cell(by_h[h]) for h in HORIZONS},
        by_skill={
            name: {h: _cell(vals[h]) for h in HORIZONS}
            for name, vals in sorted(by_skill.items())
        },
        by_lag={
            name: {h: _cell(vals[h]) for h in HORIZONS}
            for name, vals in sorted(by_lag.items())
        },
    )


def event_study_public(es: EventStudy) -> dict:
    def pack_cell(c: EventCell) -> dict:
        return {
            "n": c.n,
            "mean": round(c.mean, 4),
            "tstat": round(c.tstat, 2),
            "hit": round(c.hit, 3),
        }

    return {
        "note": es.note,
        "by_horizon": {str(h): pack_cell(c) for h, c in es.by_horizon.items()},
        "by_skill": {
            name: {str(h): pack_cell(c) for h, c in row.items()}
            for name, row in es.by_skill.items()
        },
        "by_lag": {
            name: {str(h): pack_cell(c) for h, c in row.items()}
            for name, row in es.by_lag.items()
        },
    }
