from datetime import date

from congress_alpha.calendar import daterange_trading
from congress_alpha.explain import explain_ticker
from congress_alpha.prices import PriceStore
from congress_alpha.signal import build_signals
from congress_alpha.skill import SkillBook, fit_skill
from congress_alpha.types import (
    Politician,
    Security,
    TickerSignal,
    TradeEvent,
    TradeFeatures,
)


def _book(as_of: date) -> SkillBook:
    return SkillBook(
        as_of=as_of,
        overall={"ace": 0.5},
        sector={("ace", "Defense"): 0.5},
        rows=[],
        delay_remaining={"0-7": 1.0, "8-14": 0.8, "15-30": 0.6, "31-45": 0.4, "45+": 0.3},
        premove_share={"ace": 0.02},
        overall_alpha={"ace": 0.03},
        sector_alpha={("ace", "Defense"): 0.04},
    )


def _feat(trade: TradeEvent) -> TradeFeatures:
    return TradeFeatures(
        trade=trade,
        politician_skill=0.5,
        sector_skill=0.5,
        delay_decay=0.8,
        conviction=0.5,
        confidence=0.7,
        life=1.0,
        premove_decay=0.6,
        contribution=0.4,
        on_relevant_committee=True,
    )


def test_premove_pct_is_trade_to_disclosure_not_as_of():
    """Post-filing pop must not count. trade_date is a lag endpoint, not the event."""
    trade_dt = date(2023, 5, 1)
    disc = date(2023, 6, 15)
    as_of = date(2023, 8, 1)
    px = {}
    for dt in daterange_trading(date(2023, 4, 3), date(2023, 8, 15)):
        if dt < date(2023, 5, 2):
            lmt = 100.0
        elif dt <= disc:
            lmt = 110.0
        else:
            lmt = 200.0
        px[("LMT", dt)] = lmt
        px[("SPY", dt)] = 100.0
    store = PriceStore(px)
    trade = TradeEvent("1", "ace", "LMT", trade_dt, disc, "BUY", 15001, 50000)
    politicians = [Politician("ace", "Ace Skilled", "house", "D", "VA", 10, ("hasc",))]
    securities = {"LMT": Security("LMT", "Lockheed", "Defense", "A&D", 1e9)}
    sig = TickerSignal(
        ticker="LMT",
        sector="Defense",
        as_of=as_of,
        strategy="momentum",
        raw_signal=0.4,
        n_politicians=1,
        n_predictive=1,
        n_relevant_committee=1,
        avg_lag_days=float(trade.lag_days),
        avg_premove=0.4,
        features=[_feat(trade)],
    )
    exp = explain_ticker(sig, securities, politicians, _book(as_of), store, as_of)
    assert exp["premove_pct"] == 10.0
    # If someone filled through as_of, this would be ~100%.
    as_of_move = store.holding_return("LMT", trade_dt, as_of)
    assert as_of_move is not None and as_of_move > 0.5
    assert exp["premove_pct"] < 20.0
    assert all("committee" in p for p in exp["people"])


def test_explain_toy_universe_has_premove_pct(toy):
    as_of = date(2023, 9, 1)
    book = fit_skill(as_of, toy["trades"], toy["securities"], toy["store"], toy["politicians"])
    sigs = build_signals(
        as_of,
        toy["trades"],
        book,
        toy["securities"],
        toy["politicians"],
        toy["committees"],
        toy["store"],
    )
    sig = sigs["momentum"]["LMT"]
    exp = explain_ticker(
        sig, toy["securities"], toy["politicians"], book, toy["store"], as_of
    )
    assert "premove_pct" in exp
    assert exp["premove_pct"] is not None
    expected = []
    for f in sig.features:
        xs = toy["store"].excess_return(
            f.trade.ticker,
            f.trade.trade_date,
            f.trade.disclosure_date,
            no_later_than=f.trade.disclosure_date,
        )
        if xs is not None:
            expected.append(f.trade.direction * xs)
    assert expected
    assert exp["premove_pct"] == round(100.0 * (sum(expected) / len(expected)), 1)
    # Committee remains a display flag on people, not an edge claim.
    assert all("committee" in p for p in exp["people"])
