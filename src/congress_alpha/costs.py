"""Execution costs. Applied on traded notional at the fill date, never on cash."""

from __future__ import annotations

from dataclasses import dataclass

from congress_alpha.config import (
    DEFAULT_AUM,
    DEFAULT_COMMISSION_BPS,
    DEFAULT_HALF_SPREAD_BPS,
    DEFAULT_IMPACT_K,
    MIN_DOLLAR_VOLUME,
)
from congress_alpha.types import Security


@dataclass(frozen=True)
class CostModel:
    """One-way costs in bps of |Δw| · NAV.

    spread scales with 1/sqrt(ADV). impact = k · sqrt(participation).
    """

    commission_bps: float = DEFAULT_COMMISSION_BPS
    half_spread_bps: float = DEFAULT_HALF_SPREAD_BPS
    impact_k: float = DEFAULT_IMPACT_K
    aum: float = DEFAULT_AUM

    def name_bps(self, dollar_volume: float, dw: float) -> float:
        adv = max(dollar_volume, MIN_DOLLAR_VOLUME)
        spread = self.half_spread_bps * (MIN_DOLLAR_VOLUME / adv) ** 0.5
        notional = abs(dw) * self.aum
        participation = min(notional / adv, 1.0)
        impact = self.impact_k * participation**0.5
        return self.commission_bps + spread + impact

    def trade_cost_fraction(
        self,
        old: dict[str, float],
        new: dict[str, float],
        securities: dict[str, Security],
    ) -> tuple[float, float]:
        """Return (cost as fraction of NAV, traded notional as fraction of NAV)."""
        names = set(old) | set(new)
        cost = 0.0
        traded = 0.0
        for tkr in names:
            dw = new.get(tkr, 0.0) - old.get(tkr, 0.0)
            if abs(dw) < 1e-12:
                continue
            traded += abs(dw)
            sec = securities.get(tkr)
            adv = sec.avg_dollar_volume if sec is not None else MIN_DOLLAR_VOLUME
            cost += abs(dw) * self.name_bps(adv, dw) / 1e4
        return cost, traded


def flat_cost_fraction(traded_notional: float, one_way_bps: float) -> float:
    return traded_notional * one_way_bps / 1e4
