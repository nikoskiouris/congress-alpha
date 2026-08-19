"""Long-only portfolio from signals, with stock/sector caps and cash leftover."""

from __future__ import annotations

from congress_alpha.config import (
    MIN_DOLLAR_VOLUME,
    MIN_POLITICIANS,
    MIN_SIGNAL,
    SECTOR_CAP,
    STOCK_CAP,
)
from congress_alpha.types import Portfolio, Security, TickerSignal


def construct(
    as_of,
    strategy: str,
    signals: dict[str, TickerSignal],
    securities: dict[str, Security],
    stock_cap: float = STOCK_CAP,
    sector_cap: float = SECTOR_CAP,
    min_politicians: int = MIN_POLITICIANS,
    min_signal: float = MIN_SIGNAL,
) -> Portfolio:
    eligible: dict[str, TickerSignal] = {}
    for tkr, sig in signals.items():
        if tkr not in securities:
            continue
        sec = securities[tkr]
        if sec.avg_dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        if sig.raw_signal < min_signal:
            continue
        if sig.n_politicians < min_politicians:
            continue
        eligible[tkr] = sig

    raw = {t: max(s.raw_signal, 0.0) for t, s in eligible.items()}
    total = sum(raw.values())
    if total <= 0:
        return Portfolio(as_of, strategy, {}, 1.0, eligible)

    w = {t: v / total for t, v in raw.items()}
    sectors = {t: securities[t].sector for t in w}

    for _ in range(16):
        for t, wt in list(w.items()):
            if wt > stock_cap:
                w[t] = stock_cap
        by_sec: dict[str, float] = {}
        for t, wt in w.items():
            by_sec[sectors[t]] = by_sec.get(sectors[t], 0.0) + wt
        for sec, sw in by_sec.items():
            if sw > sector_cap:
                scale = sector_cap / sw
                for t in w:
                    if sectors[t] == sec:
                        w[t] *= scale
        s = sum(w.values())
        if s > 1.0:
            w = {t: wt / s for t, wt in w.items()}

    invested = sum(w.values())
    cash = max(0.0, 1.0 - invested)
    w = {t: wt for t, wt in w.items() if wt > 1e-6}
    return Portfolio(as_of, strategy, w, cash, eligible)
