from datetime import date

from congress_alpha.config import STOCK_CAP
from congress_alpha.portfolio import construct
from congress_alpha.skill import conviction_and_confidence, lag_bucket, life_weight
from congress_alpha.types import Security, TickerSignal


def test_life_expires():
    assert life_weight(-1) == 0
    assert life_weight(0) == 1
    assert life_weight(20) == 1
    assert 0 < life_weight(50) < 1
    assert life_weight(90) == 0


def test_lag_buckets():
    assert lag_bucket(3) == "0-7"
    assert lag_bucket(12) == "8-14"
    assert lag_bucket(40) == "31-45"
    assert lag_bucket(60) == "45+"


def test_conviction_not_naive_midpoint():
    # Wide band is less confident than a tight band around the same geom mid-ish.
    c1, conf1 = conviction_and_confidence(15_001, 50_000)
    c2, conf2 = conviction_and_confidence(100_001, 250_000)
    assert c2 > c1
    tight, tconf = conviction_and_confidence(49_000, 51_000)
    wide, wconf = conviction_and_confidence(1_001, 50_000)
    assert tconf > wconf


def test_stock_and_sector_caps():
    secs = {
        "LMT": Security("LMT", "L", "Defense", "x", 1e9),
        "RTX": Security("RTX", "R", "Defense", "x", 1e9),
        "NOC": Security("NOC", "N", "Defense", "x", 1e9),
        "NVDA": Security("NVDA", "N", "Technology", "x", 1e9),
        "MSFT": Security("MSFT", "M", "Technology", "x", 1e9),
        "JPM": Security("JPM", "J", "Financials", "x", 1e9),
    }

    def sig(tkr, sector, val):
        return TickerSignal(
            ticker=tkr,
            sector=sector,
            as_of=date(2024, 1, 1),
            strategy="momentum",
            raw_signal=val,
            n_politicians=3,
            n_predictive=3,
            n_relevant_committee=1,
            avg_lag_days=10,
            avg_premove=0.0,
        )

    signals = {
        "LMT": sig("LMT", "Defense", 9.0),
        "RTX": sig("RTX", "Defense", 8.0),
        "NOC": sig("NOC", "Defense", 7.0),
        "NVDA": sig("NVDA", "Technology", 2.0),
        "MSFT": sig("MSFT", "Technology", 1.5),
        "JPM": sig("JPM", "Financials", 1.2),
    }
    port = construct(date(2024, 1, 1), "momentum", signals, secs)
    assert all(w <= STOCK_CAP + 1e-9 for w in port.weights.values())
    by_sec = {}
    for t, w in port.weights.items():
        by_sec[secs[t].sector] = by_sec.get(secs[t].sector, 0.0) + w
    assert all(v <= 0.30 + 1e-9 for v in by_sec.values())
    assert abs(sum(port.weights.values()) + port.cash - 1.0) < 1e-6


def test_min_politicians_gate():
    secs = {"LMT": Security("LMT", "L", "Defense", "x", 1e9)}
    lonely = TickerSignal(
        ticker="LMT",
        sector="Defense",
        as_of=date(2024, 1, 1),
        strategy="momentum",
        raw_signal=5.0,
        n_politicians=1,
        n_predictive=1,
        n_relevant_committee=1,
        avg_lag_days=8,
        avg_premove=0.0,
    )
    port = construct(date(2024, 1, 1), "momentum", {"LMT": lonely}, secs)
    assert "LMT" not in port.weights
    assert port.cash == 1.0
