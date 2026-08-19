"""Human-readable WHY panel for a ticker signal."""

from __future__ import annotations

from datetime import date

from congress_alpha.prices import PriceStore
from congress_alpha.skill import SkillBook
from congress_alpha.types import Politician, Security, TickerSignal


def congress_score(signals: dict[str, TickerSignal]) -> tuple[int, str]:
    """Map net congressional flow to a 0-100 score. 50 = neutral."""
    import math

    pos = sum(max(s.raw_signal, 0.0) for s in signals.values())
    neg = sum(max(-s.raw_signal, 0.0) for s in signals.values())
    net = pos - neg
    scale = max(pos + neg, 0.75)
    score = 50 + 42 * math.tanh(net / scale)
    score_i = int(round(max(0, min(100, score))))
    if score_i >= 60:
        label = "BULLISH"
    elif score_i <= 40:
        label = "BEARISH"
    else:
        label = "NEUTRAL"
    return score_i, label


def explain_ticker(
    sig: TickerSignal,
    securities: dict[str, Security],
    politicians: list[Politician],
    book: SkillBook,
    store: PriceStore,
    as_of: date,
) -> dict:
    names = {p.politician_id: p.name for p in politicians}
    sec = securities[sig.ticker]
    contribs = sorted(sig.features, key=lambda f: abs(f.contribution), reverse=True)
    people = []
    for f in contribs[:8]:
        people.append(
            {
                "name": names.get(f.trade.politician_id, f.trade.politician_id),
                "politician_id": f.trade.politician_id,
                "side": f.trade.side,
                "lag_days": f.trade.lag_days,
                "disclosure_date": f.trade.disclosure_date.isoformat(),
                "trade_date": f.trade.trade_date.isoformat(),
                "weight": round(f.sector_skill, 3),
                "contribution": round(f.contribution, 3),
                "committee": f.on_relevant_committee,
                "amount_min": f.trade.amount_min,
                "amount_max": f.trade.amount_max,
            }
        )

    pre_move = store.return_between(
        sig.ticker,
        min((f.trade.trade_date for f in sig.features), default=as_of),
        as_of,
    )
    sector_alphas = [
        book.sector_alpha.get((f.trade.politician_id, sig.sector), 0.0)
        for f in sig.features
        if f.politician_skill > 0
    ]
    mean_sec_alpha = sum(sector_alphas) / len(sector_alphas) if sector_alphas else 0.0

    positives = []
    negatives = []
    if sig.n_predictive:
        positives.append(
            f"{sig.n_predictive} historically predictive politician"
            f"{'s' if sig.n_predictive != 1 else ''} on this name"
        )
    if sig.n_relevant_committee:
        positives.append(
            f"{sig.n_relevant_committee} filer"
            f"{'s sit' if sig.n_relevant_committee != 1 else ' sits'} on a {sig.sector.lower()}-relevant committee"
        )
    if sig.n_politicians >= 3:
        positives.append("unusually strong congressional accumulation")
    if sig.avg_lag_days and sig.avg_lag_days <= 14:
        positives.append(f"average disclosure lag only {sig.avg_lag_days:.0f} days")
    if mean_sec_alpha > 0.01:
        positives.append(
            f"politician–{sig.sector.lower()} historical post-disclosure alpha: {mean_sec_alpha:+.1%}"
        )
    if pre_move is not None and pre_move > 0.06:
        negatives.append(
            f"stock already {pre_move:+.1%} since earliest contributing trade date"
        )
    decayed = 1.0 - (sum(f.life * f.delay_decay * f.premove_decay for f in sig.features) / max(len(sig.features), 1))
    if decayed > 0.4:
        negatives.append(f"about {decayed:.0%} of estimated signal has already decayed")

    raw = sig.raw_signal
    score = int(round(100 * _squash(raw)))
    return {
        "ticker": sig.ticker,
        "name": sec.name,
        "sector": sig.sector,
        "strategy": sig.strategy,
        "signal": round(raw, 4),
        "score": score,
        "n_politicians": sig.n_politicians,
        "n_predictive": sig.n_predictive,
        "n_relevant_committee": sig.n_relevant_committee,
        "avg_lag_days": round(sig.avg_lag_days, 1),
        "positives": positives,
        "negatives": negatives,
        "people": people,
        "pre_move": None if pre_move is None else round(pre_move, 4),
        "sector_alpha": round(mean_sec_alpha, 4),
        "decayed_frac": round(max(decayed, 0.0), 3),
        "blurb": _blurb(sig, positives, negatives, decayed),
    }


def _squash(x: float) -> float:
    import math

    return 1.0 / (1.0 + math.exp(-x))


def _blurb(sig: TickerSignal, pos: list[str], neg: list[str], decayed: float) -> str:
    bits = []
    if sig.n_predictive:
        bits.append(
            f"{sig.n_predictive} independently predictive congressional trader"
            f"{'s' if sig.n_predictive != 1 else ''} recently accumulated it"
        )
    if sig.n_relevant_committee:
        bits.append(f"{sig.n_relevant_committee} sit on a relevant committee")
    bits.append(f"only {decayed:.0%} of estimated signal has decayed since the filings")
    lead = ", ".join(bits[:2]) if bits else "disclosed congressional flow"
    return (
        f"CongressModel currently flags {sig.ticker} because {lead}."
    )
