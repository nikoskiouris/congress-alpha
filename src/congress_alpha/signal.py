"""Aggregate disclosed trades into a Congress Alpha signal.

Signal_{stock,t} = sum_p w_{p,s,t} * s_{p,stock,t}

A trade contributes only if disclosure_date <= as_of. The live model never
sees the private trade_date as an event time; lag is a feature, not a clock.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from congress_alpha.config import (
    CONSENSUS_MIN_POLITICIANS,
    CONSENSUS_WINDOW_DAYS,
    CONVICTION_MIN_WEIGHT,
    STRATEGIES,
)
from congress_alpha.prices import PriceStore
from congress_alpha.skill import (
    SkillBook,
    conviction_and_confidence,
    lag_bucket,
    life_weight,
    politician_sector_weight,
)
from congress_alpha.types import (
    Committee,
    Politician,
    Security,
    TickerSignal,
    TradeEvent,
    TradeFeatures,
)

COMMITTEE_SECTOR = None  # filled from committees at runtime


def _committee_sector(committees: dict[str, Committee], politician: Politician) -> set[str]:
    return {committees[c].primary_sector for c in politician.committee_ids if c in committees}


def _premove_decay(book: SkillBook, pid: str, this_premove: float) -> float:
    """If the stock already did the politician's typical whole move before
    the filing hit, ignore the trade."""
    typical_pre = book.premove_share.get(pid, 0.0)
    typical_post = book.overall_alpha.get(pid, 0.0)
    expected_total = typical_pre + max(typical_post, 0.0)
    if expected_total <= 1e-4:
        # No historical edge: still penalize huge already-happened pops.
        if this_premove > 0.08:
            return 0.25
        return 1.0
    realized_frac = this_premove / expected_total
    if realized_frac <= 0:
        return 1.0
    return float(max(0.0, 1.0 - 0.85 * realized_frac))


def _trade_feature(
    tr: TradeEvent,
    as_of: date,
    book: SkillBook,
    securities: dict[str, Security],
    politicians: dict[str, Politician],
    committees: dict[str, Committee],
    store: PriceStore,
) -> TradeFeatures | None:
    if tr.disclosure_date > as_of:
        return None
    life = life_weight((as_of - tr.disclosure_date).days)
    if life <= 0:
        return None
    if tr.ticker not in securities:
        return None
    sec = securities[tr.ticker].sector
    p_skill = book.overall.get(tr.politician_id, 0.0)
    s_skill = politician_sector_weight(book, tr.politician_id, sec)
    decay = book.delay_remaining.get(lag_bucket(tr.lag_days), 0.5)
    conv, conf = conviction_and_confidence(tr.amount_min, tr.amount_max)
    pre = store.excess_return(tr.ticker, tr.trade_date, tr.disclosure_date)
    this_pre = (tr.direction * pre) if pre is not None else 0.0
    prem = _premove_decay(book, tr.politician_id, this_pre)
    pol = politicians.get(tr.politician_id)
    on_c = False
    if pol:
        on_c = sec in _committee_sector(committees, pol)
    contrib = (
        tr.direction
        * s_skill
        * decay
        * conv
        * conf
        * life
        * prem
    )
    return TradeFeatures(
        trade=tr,
        politician_skill=p_skill,
        sector_skill=s_skill,
        delay_decay=decay,
        conviction=conv,
        confidence=conf,
        life=life,
        premove_decay=prem,
        contribution=contrib,
        on_relevant_committee=on_c,
    )


def _pack(
    ticker: str,
    sector: str,
    as_of: date,
    strategy: str,
    feats: list[TradeFeatures],
) -> TickerSignal:
    raw = sum(f.contribution for f in feats)
    pids = {f.trade.politician_id for f in feats}
    predictive = {f.trade.politician_id for f in feats if f.politician_skill > 0}
    n_c = len({f.trade.politician_id for f in feats if f.on_relevant_committee})
    lags = [f.trade.lag_days for f in feats]
    pres = []
    for f in feats:
        # already-moved since trade: use 1 - premove_decay as a proxy later in explain
        pres.append(1.0 - f.premove_decay)
    return TickerSignal(
        ticker=ticker,
        sector=sector,
        as_of=as_of,
        strategy=strategy,
        raw_signal=raw,
        n_politicians=len(pids),
        n_predictive=len(predictive),
        n_relevant_committee=n_c,
        avg_lag_days=sum(lags) / len(lags) if lags else 0.0,
        avg_premove=sum(pres) / len(pres) if pres else 0.0,
        features=feats,
    )


def build_signals(
    as_of: date,
    trades: list[TradeEvent],
    book: SkillBook,
    securities: dict[str, Security],
    politicians: list[Politician],
    committees: dict[str, Committee],
    store: PriceStore,
) -> dict[str, dict[str, TickerSignal]]:
    """strategy -> ticker -> TickerSignal"""
    pols = {p.politician_id: p for p in politicians}
    by_ticker: dict[str, list[TradeFeatures]] = defaultdict(list)
    for tr in trades:
        feat = _trade_feature(tr, as_of, book, securities, pols, committees, store)
        if feat is None:
            continue
        by_ticker[tr.ticker].append(feat)

    out: dict[str, dict[str, TickerSignal]] = {s: {} for s in STRATEGIES}
    for ticker, feats in by_ticker.items():
        sector = securities[ticker].sector

        # Momentum: all recent disclosed flow, skill-weighted.
        out["momentum"][ticker] = _pack(ticker, sector, as_of, "momentum", feats)

        # Conviction: only historically predictive politicians.
        conv_feats = [
            f
            for f in feats
            if f.politician_skill >= CONVICTION_MIN_WEIGHT
        ]
        if conv_feats:
            out["conviction"][ticker] = _pack(
                ticker, sector, as_of, "conviction", conv_feats
            )

        # Consensus: several independent politicians, same direction, recent window.
        recent = [
            f
            for f in feats
            if (as_of - f.trade.disclosure_date).days <= CONSENSUS_WINDOW_DAYS
        ]
        buys = [f for f in recent if f.trade.side == "BUY" and f.politician_skill > 0]
        sells = [f for f in recent if f.trade.side == "SELL" and f.politician_skill > 0]
        buy_ids = {f.trade.politician_id for f in buys}
        sell_ids = {f.trade.politician_id for f in sells}
        if len(buy_ids) >= CONSENSUS_MIN_POLITICIANS and len(buy_ids) >= len(sell_ids):
            out["consensus"][ticker] = _pack(ticker, sector, as_of, "consensus", buys)
        elif len(sell_ids) >= CONSENSUS_MIN_POLITICIANS:
            out["consensus"][ticker] = _pack(ticker, sector, as_of, "consensus", sells)

    return out
