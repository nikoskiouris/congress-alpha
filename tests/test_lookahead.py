from datetime import date

from congress_alpha.portfolio import construct
from congress_alpha.signal import build_signals
from congress_alpha.skill import fit_skill


def test_future_disclosure_is_invisible(toy):
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
    feats = sigs["momentum"]["LMT"].features
    ids = {f.trade.trade_id for f in feats}
    assert "5" not in ids
    assert "1" in ids or "2" in ids


def test_signal_appears_on_disclosure_date(toy):
    before = date(2023, 6, 14)
    on = date(2023, 6, 15)
    book_b = fit_skill(before, toy["trades"], toy["securities"], toy["store"], toy["politicians"])
    book_o = fit_skill(on, toy["trades"], toy["securities"], toy["store"], toy["politicians"])
    s_before = build_signals(
        before, toy["trades"], book_b, toy["securities"], toy["politicians"], toy["committees"], toy["store"]
    )
    s_on = build_signals(
        on, toy["trades"], book_o, toy["securities"], toy["politicians"], toy["committees"], toy["store"]
    )
    ids_before = {f.trade.trade_id for f in s_before.get("momentum", {}).get("LMT", type("X", (), {"features": []})).features} if "LMT" in s_before.get("momentum", {}) else set()
    # trade 1 discloses on 2023-06-15
    if "LMT" in s_before.get("momentum", {}):
        assert "1" not in {f.trade.trade_id for f in s_before["momentum"]["LMT"].features}
    assert "1" in {f.trade.trade_id for f in s_on["momentum"]["LMT"].features}


def test_skill_uses_completed_windows_only(toy):
    # Too early: trade 1's 120d window has not closed, so ace should not be
    # trained on a still-open outcome.
    early = date(2023, 6, 16)
    book = fit_skill(early, toy["trades"], toy["securities"], toy["store"], toy["politicians"])
    assert abs(book.overall.get("ace", 0.0)) < 0.05

    late = date(2024, 3, 1)
    book2 = fit_skill(late, toy["trades"], toy["securities"], toy["store"], toy["politicians"])
    # Ace bought LMT which drifted after disclosure. Noise bought AAPL which did not.
    assert book2.overall["ace"] > book2.overall["noise"]
