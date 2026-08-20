"""Model constants. Change these; do not hide look-ahead in defaults."""

from __future__ import annotations

HORIZONS = (5, 20, 60, 120)

# Blend of post-disclosure horizon alphas into one politician skill score.
# 20d and 60d dominate because those are the windows a public filer can actually trade.
HORIZON_BLEND = {5: 0.15, 20: 0.40, 60: 0.30, 120: 0.15}

LAG_BUCKETS = (
    (0, 7, "0-7"),
    (8, 14, "8-14"),
    (15, 30, "15-30"),
    (31, 45, "31-45"),
    (46, 10_000, "45+"),
)

SIGNAL_EXPIRY_DAYS = 90
SIGNAL_FULL_LIFE_DAYS = 20

STOCK_CAP = 0.10
SECTOR_CAP = 0.30
MIN_POLITICIANS = 2
MIN_SIGNAL = 0.05
MIN_DOLLAR_VOLUME = 5_000_000.0

# Empirical-Bayes shrinkage: small samples pulled toward zero skill.
SKILL_PRIOR_N = 12.0
SECTOR_PRIOR_N = 8.0
DELAY_PRIOR_N = 20.0

RECENCY_HALFLIFE_DAYS = 365 * 2

# Conviction uses geometric midpoint of the STOCK Act amount band.
CONVICTION_REF = 1_000_000.0

# Strategy knobs
CONVICTION_MIN_WEIGHT = 0.25
CONSENSUS_MIN_POLITICIANS = 3
CONSENSUS_WINDOW_DAYS = 21

BENCHMARK = "SPY"
CASH = "CASH"

STRATEGIES = ("momentum", "conviction", "consensus")

# Portfolio fills the next session after the signal date. Same-day close would
# pretend a 4pm filing was tradable at that day's close.
EXECUTION_LAG_SESSIONS = 1
# Skill labels use the same entry lag so training matches tradable P&L.
LABEL_ENTRY_LAG_SESSIONS = 1

# Default research book for market-impact scaling. Not a live AUM claim.
DEFAULT_AUM = 10_000_000.0
# Flat one-way cost used in the cost sweep (bps of traded notional).
COST_SWEEP_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
DEFAULT_COMMISSION_BPS = 1.0
DEFAULT_HALF_SPREAD_BPS = 4.0
DEFAULT_IMPACT_K = 5.0

# Extra calendar days after a label window closes before the weight may be used.
# 0 is already nested (end < as_of). Raise this to add a purge gap.
LABEL_EMBARGO_DAYS = 0

# STOCK Act value bands used when a filing only reports a range.
AMOUNT_BANDS = (
    (1_001.0, 15_000.0),
    (15_001.0, 50_000.0),
    (50_001.0, 100_000.0),
    (100_001.0, 250_000.0),
    (250_001.0, 500_000.0),
    (500_001.0, 1_000_000.0),
    (1_000_001.0, 5_000_000.0),
    (5_000_001.0, 25_000_000.0),
)
