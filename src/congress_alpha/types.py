from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Side = Literal["BUY", "SELL"]
Strategy = Literal["momentum", "conviction", "consensus"]


@dataclass(frozen=True)
class Politician:
    politician_id: str
    name: str
    chamber: str
    party: str
    state: str
    seniority_years: float
    committee_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Committee:
    committee_id: str
    name: str
    chamber: str
    primary_sector: str


@dataclass(frozen=True)
class Security:
    ticker: str
    name: str
    sector: str
    industry: str
    avg_dollar_volume: float


@dataclass(frozen=True)
class TradeEvent:
    trade_id: str
    politician_id: str
    ticker: str
    trade_date: date
    disclosure_date: date
    side: Side
    amount_min: float
    amount_max: float
    owner: str = "self"
    source: str = "synthetic"

    @property
    def lag_days(self) -> int:
        return (self.disclosure_date - self.trade_date).days

    @property
    def direction(self) -> float:
        return 1.0 if self.side == "BUY" else -1.0

    @property
    def geom_mid(self) -> float:
        return (self.amount_min * self.amount_max) ** 0.5


@dataclass
class TradeFeatures:
    """Point-in-time contribution of one disclosed trade to one ticker signal."""

    trade: TradeEvent
    politician_skill: float
    sector_skill: float
    delay_decay: float
    conviction: float
    confidence: float
    life: float
    premove_decay: float
    contribution: float
    on_relevant_committee: bool


@dataclass
class TickerSignal:
    ticker: str
    sector: str
    as_of: date
    strategy: str
    raw_signal: float
    n_politicians: int
    n_predictive: int
    n_relevant_committee: int
    avg_lag_days: float
    avg_premove: float
    features: list[TradeFeatures] = field(default_factory=list)


@dataclass
class Portfolio:
    as_of: date
    strategy: str
    weights: dict[str, float]
    cash: float
    signals: dict[str, TickerSignal]


@dataclass
class SkillRow:
    politician_id: str
    sector: str | None
    horizon: int
    alpha: float
    hit_rate: float
    n: float
    weight: float


@dataclass
class BacktestPoint:
    date: date
    strategy: str
    nav: float
    daily_return: float
    excess_return: float
    n_holdings: int
    invested: float
    gross_return: float = 0.0
    cost: float = 0.0
    turnover: float = 0.0
    cash: float = 0.0
    signal_date: date | None = None
