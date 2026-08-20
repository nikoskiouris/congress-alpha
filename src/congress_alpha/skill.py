"""Point-in-time politician skill, sector skill, and disclosure-delay decay.

CRITICAL: every alpha is measured from disclosure_date, never trade_date.
A trade is eligible for training only after its evaluation window has closed:
    disclosure_date + horizon < as_of
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import log

import numpy as np

from congress_alpha.calendar import add_trading_days
from congress_alpha.config import (
    BENCHMARK,
    CONVICTION_REF,
    DELAY_PRIOR_N,
    HORIZON_BLEND,
    HORIZONS,
    LABEL_EMBARGO_DAYS,
    LABEL_ENTRY_LAG_SESSIONS,
    LAG_BUCKETS,
    RECENCY_HALFLIFE_DAYS,
    SECTOR_PRIOR_N,
    SIGNAL_EXPIRY_DAYS,
    SIGNAL_FULL_LIFE_DAYS,
    SKILL_PRIOR_N,
)
from congress_alpha.prices import PriceStore
from congress_alpha.types import Politician, Security, SkillRow, TradeEvent


def lag_bucket(lag_days: int) -> str:
    for lo, hi, name in LAG_BUCKETS:
        if lo <= lag_days <= hi:
            return name
    return "45+"


def recency_weight(disclosure_date: date, as_of: date) -> float:
    age = max((as_of - disclosure_date).days, 0)
    return 0.5 ** (age / RECENCY_HALFLIFE_DAYS)


def conviction_and_confidence(amount_min: float, amount_max: float) -> tuple[float, float]:
    """Log-scaled geometric midpoint + range-width confidence.

    A $15k–$50k band is not treated as exactly $32.5k. Wider bands get
    lower confidence; larger geometric mids get higher conviction.
    """
    mid = (max(amount_min, 1.0) * max(amount_max, 1.0)) ** 0.5
    conviction = float(np.clip(log(mid) / log(CONVICTION_REF), 0.20, 1.60))
    ratio = max(amount_max, 1.0) / max(amount_min, 1.0)
    confidence = float(1.0 / (1.0 + log(max(ratio, 1.01))))
    return conviction, confidence


def life_weight(days_since_disclosure: int) -> float:
    if days_since_disclosure < 0 or days_since_disclosure >= SIGNAL_EXPIRY_DAYS:
        return 0.0
    if days_since_disclosure <= SIGNAL_FULL_LIFE_DAYS:
        return 1.0
    return 1.0 - (days_since_disclosure - SIGNAL_FULL_LIFE_DAYS) / (
        SIGNAL_EXPIRY_DAYS - SIGNAL_FULL_LIFE_DAYS
    )


def _shrink(mean: float, n: float, prior: float, n_prior: float) -> float:
    return (n * mean + n_prior * prior) / (n + n_prior)


@dataclass
class TradeAlphaCache:
    post: dict[str, dict[int, float | None]]
    pre: dict[str, float | None]


def precompute_trade_alphas(
    trades: list[TradeEvent], store: PriceStore
) -> TradeAlphaCache:
    return TradeAlphaCache(post=_alpha_map(trades, store), pre=_premove(trades, store))


@dataclass
class SkillBook:
    as_of: date
    # politician -> blended overall weight
    overall: dict[str, float]
    # (politician, sector) -> blended sector weight
    sector: dict[tuple[str, str], float]
    rows: list[SkillRow]
    delay_remaining: dict[str, float]
    # politician -> mean pre-disclosure excess (for already-moved penalty)
    premove_share: dict[str, float]
    sample_n: dict[str, float] = field(default_factory=dict)
    sector_n: dict[tuple[str, str], float] = field(default_factory=dict)
    overall_alpha: dict[str, float] = field(default_factory=dict)
    sector_alpha: dict[tuple[str, str], float] = field(default_factory=dict)
    hit_rate: dict[str, float] = field(default_factory=dict)


def label_window(disclosure: date, horizon: int) -> tuple[date, date]:
    """Tradable window: next session after disclosure, then `horizon` trading days."""
    entry = add_trading_days(disclosure, LABEL_ENTRY_LAG_SESSIONS)
    end = add_trading_days(entry, horizon)
    return entry, end


def _completed(trade: TradeEvent, as_of: date, horizon: int) -> bool:
    _, end = label_window(trade.disclosure_date, horizon)
    return end + timedelta(days=LABEL_EMBARGO_DAYS) < as_of


def _alpha_map(
    trades: list[TradeEvent], store: PriceStore
) -> dict[str, dict[int, float | None]]:
    """trade_id -> {horizon: post-disclosure excess alpha}."""
    out: dict[str, dict[int, float | None]] = {}
    for tr in trades:
        by_h: dict[int, float | None] = {}
        for h in HORIZONS:
            entry, end = label_window(tr.disclosure_date, h)
            xs = store.excess_return(
                tr.ticker, entry, end, BENCHMARK, no_later_than=end
            )
            if xs is None:
                by_h[h] = None
            else:
                by_h[h] = tr.direction * xs
        out[tr.trade_id] = by_h
    return out


def _premove(trades: list[TradeEvent], store: PriceStore) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for tr in trades:
        xs = store.excess_return(tr.ticker, tr.trade_date, tr.disclosure_date, BENCHMARK)
        if xs is None:
            out[tr.trade_id] = None
        else:
            out[tr.trade_id] = tr.direction * xs
    return out


def fit_skill(
    as_of: date,
    trades: list[TradeEvent],
    securities: dict[str, Security],
    store: PriceStore,
    politicians: list[Politician] | None = None,
    cache: TradeAlphaCache | None = None,
) -> SkillBook:
    alphas = cache.post if cache else _alpha_map(trades, store)
    pre = cache.pre if cache else _premove(trades, store)
    pids = {t.politician_id for t in trades}
    if politicians:
        pids |= {p.politician_id for p in politicians}

    by_pid: dict[str, list[TradeEvent]] = defaultdict(list)
    for tr in trades:
        by_pid[tr.politician_id].append(tr)

    rows: list[SkillRow] = []
    overall_w: dict[str, float] = {}
    sector_w: dict[tuple[str, str], float] = {}
    sample_n: dict[str, float] = {}
    sector_n: dict[tuple[str, str], float] = {}
    overall_alpha: dict[str, float] = {}
    sector_alpha: dict[tuple[str, str], float] = {}
    hit_rate: dict[str, float] = {}
    premove_share: dict[str, float] = {}

    # Delay-decay: remaining tradable alpha by lag bucket, relative to 0-7.
    bucket_vals: dict[str, list[tuple[float, float]]] = {b[2]: [] for b in LAG_BUCKETS}

    for pid in sorted(pids):
        mine = by_pid.get(pid, [])
        blended = 0.0
        n_blend = 0.0
        hits = 0.0
        hit_w = 0.0
        pre_vals: list[tuple[float, float]] = []
        for h, h_w in HORIZON_BLEND.items():
            ws: list[float] = []
            vs: list[float] = []
            for tr in mine:
                if not _completed(tr, as_of, h):
                    continue
                a = alphas[tr.trade_id].get(h)
                if a is None:
                    continue
                w = recency_weight(tr.disclosure_date, as_of)
                ws.append(w)
                vs.append(a)
                if h == 20:
                    bucket_vals[lag_bucket(tr.lag_days)].append((w, a))
                    pv = pre[tr.trade_id]
                    if pv is not None:
                        pre_vals.append((w, pv))
            n = float(len(vs))
            if n == 0:
                mean = 0.0
                hr = 0.5
            else:
                wsum = sum(ws) or 1.0
                mean = sum(w * v for w, v in zip(ws, vs)) / wsum
                hr = sum(w for w, v in zip(ws, vs) if v > 0) / wsum
            shrunk = _shrink(mean, n, 0.0, SKILL_PRIOR_N)
            # Convert alpha into a bounded weight. ~8% 20d alpha -> weight ~1.
            weight = float(np.tanh(shrunk / 0.06) * (n / (n + 6.0)))
            rows.append(
                SkillRow(pid, "ALL", h, shrunk, hr, n, weight)
            )
            blended += h_w * weight
            n_blend += h_w * n
            if h == 20:
                hits = hr
                hit_w = n
                overall_alpha[pid] = shrunk
        overall_w[pid] = float(blended)
        sample_n[pid] = n_blend
        hit_rate[pid] = hits if hit_w else 0.5
        if pre_vals:
            wsum = sum(w for w, _ in pre_vals) or 1.0
            premove_share[pid] = sum(w * v for w, v in pre_vals) / wsum
        else:
            premove_share[pid] = 0.0

        # Politician × sector
        secs = sorted(
            {
                securities[t.ticker].sector
                for t in mine
                if t.ticker in securities
            }
        )
        for sec in secs:
            blended_s = 0.0
            n_s = 0.0
            alpha_s = 0.0
            for h, h_w in HORIZON_BLEND.items():
                ws, vs = [], []
                for tr in mine:
                    if tr.ticker not in securities:
                        continue
                    if securities[tr.ticker].sector != sec:
                        continue
                    if not _completed(tr, as_of, h):
                        continue
                    a = alphas[tr.trade_id].get(h)
                    if a is None:
                        continue
                    w = recency_weight(tr.disclosure_date, as_of)
                    ws.append(w)
                    vs.append(a)
                n = float(len(vs))
                mean = (
                    sum(w * v for w, v in zip(ws, vs)) / (sum(ws) or 1.0) if vs else 0.0
                )
                shrunk = _shrink(mean, n, overall_alpha.get(pid, 0.0), SECTOR_PRIOR_N)
                weight = float(np.tanh(shrunk / 0.06) * (n / (n + 4.0)))
                rows.append(SkillRow(pid, sec, h, shrunk, 0.0, n, weight))
                blended_s += h_w * weight
                n_s += h_w * n
                if h == 20:
                    alpha_s = shrunk
            sector_w[(pid, sec)] = float(blended_s)
            sector_n[(pid, sec)] = n_s
            sector_alpha[(pid, sec)] = alpha_s

    # Delay remaining: normalize 20d post-disclosure alpha by the 0-7 bucket.
    raw: dict[str, float] = {}
    ns: dict[str, float] = {}
    for name, pairs in bucket_vals.items():
        if not pairs:
            raw[name] = 0.0
            ns[name] = 0.0
            continue
        wsum = sum(w for w, _ in pairs) or 1.0
        raw[name] = sum(w * v for w, v in pairs) / wsum
        ns[name] = float(len(pairs))
    base = raw.get("0-7", 0.0)
    delay_remaining: dict[str, float] = {}
    for name in raw:
        if base > 1e-6:
            empirical = max(raw[name] / base, 0.0)
        else:
            empirical = 1.0
        # Shrink noisy buckets toward a simple exponential prior.
        lo = next(b[0] for b in LAG_BUCKETS if b[2] == name)
        prior = float(np.exp(-0.035 * lo))
        delay_remaining[name] = float(
            np.clip(_shrink(empirical, ns[name], prior, DELAY_PRIOR_N), 0.02, 1.25)
        )

    return SkillBook(
        as_of=as_of,
        overall=overall_w,
        sector=sector_w,
        rows=rows,
        delay_remaining=delay_remaining,
        premove_share=premove_share,
        sample_n=sample_n,
        sector_n=sector_n,
        overall_alpha=overall_alpha,
        sector_alpha=sector_alpha,
        hit_rate=hit_rate,
    )


def politician_sector_weight(book: SkillBook, pid: str, sector: str) -> float:
    overall = book.overall.get(pid, 0.0)
    keyed = book.sector.get((pid, sector))
    if keyed is None:
        return overall
    n_s = book.sector_n.get((pid, sector), 0.0)
    # Blend: don't trust a 2-trade sector sample over the politician's overall record.
    return (n_s * keyed + SECTOR_PRIOR_N * overall) / (n_s + SECTOR_PRIOR_N)
