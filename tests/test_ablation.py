from datetime import date, timedelta

import numpy as np
import pytest

from congress_alpha.ablation import equal_skill_book, no_delay_book, permute_skill_book
from congress_alpha.backtest import run_backtest
from congress_alpha.calendar import add_trading_days, daterange_trading
from congress_alpha.costs import CostModel
from congress_alpha.prices import PriceStore
from congress_alpha.skill import SkillBook
from congress_alpha.types import Committee, Politician, Security, TradeEvent


def _book(**kwargs) -> SkillBook:
    fields = dict(
        as_of=date(2023, 9, 1),
        overall={"ace": 0.80, "bob": 0.10, "noise": -0.20},
        sector={
            ("ace", "Defense"): 0.90,
            ("bob", "Tech"): 0.05,
            ("noise", "Defense"): -0.10,
        },
        rows=[],
        delay_remaining={
            "0-7": 1.0,
            "8-14": 0.7,
            "15-30": 0.4,
            "31-45": 0.2,
            "45+": 0.05,
        },
        premove_share={"ace": 0.02, "bob": 0.0, "noise": 0.01},
    )
    fields.update(kwargs)
    return SkillBook(**fields)


def test_equal_skill_book_sets_weights_and_leaves_original():
    book = _book()
    orig_overall = dict(book.overall)
    orig_sector = dict(book.sector)
    orig_delay = dict(book.delay_remaining)
    out = equal_skill_book(book)
    assert all(v == pytest.approx(0.40) for v in out.overall.values())
    assert set(out.overall) == set(orig_overall)
    assert all(v == pytest.approx(0.40) for v in out.sector.values())
    assert book.overall == orig_overall
    assert book.sector == orig_sector
    assert book.delay_remaining == orig_delay
    assert out.overall is not book.overall


def test_no_delay_book_sets_buckets_and_leaves_original():
    book = _book()
    orig_delay = dict(book.delay_remaining)
    orig_overall = dict(book.overall)
    out = no_delay_book(book)
    assert all(v == pytest.approx(1.0) for v in out.delay_remaining.values())
    assert set(out.delay_remaining) == set(orig_delay)
    assert book.delay_remaining == orig_delay
    assert book.overall == orig_overall
    assert orig_delay["8-14"] != pytest.approx(1.0)


def test_permute_skill_book_is_permutation_not_identity():
    overall = {f"p{i}": round(0.11 * i - 0.25, 4) for i in range(8)}
    sector = {(f"p{i}", "Defense"): round(0.05 * i, 4) for i in range(8)}
    book = _book(overall=overall, sector=sector)
    orig_overall = dict(book.overall)
    orig_sector = dict(book.sector)
    out = permute_skill_book(book, np.random.default_rng(7))
    assert set(out.overall.values()) == set(orig_overall.values())
    assert set(out.overall) == set(orig_overall)
    assert out.overall != orig_overall
    assert {sec for (_, sec) in out.sector} == {"Defense"}
    assert set(out.sector.values()) == set(orig_sector.values())
    assert book.overall == orig_overall
    assert book.sector == orig_sector


def _tiny_walk_forward():
    start = date(2023, 1, 2)
    end = date(2023, 10, 31)
    sessions = daterange_trading(start, end)
    politicians = [
        Politician("ace", "Ace", "house", "D", "VA", 10, ("hasc",)),
        Politician("bob", "Bob", "house", "R", "AZ", 8, ()),
    ]
    committees = {"hasc": Committee("hasc", "Armed Services", "house", "Defense")}
    securities = {
        "LMT": Security("LMT", "Lockheed", "Defense", "A&D", 1e9),
        "SPY": Security("SPY", "SPY", "Market", "Index", 1e11),
    }
    px = {}
    spy = 100.0
    lmt = 100.0
    for dt in sessions:
        spy *= 1.0002
        lmt *= 1.0015
        px[("SPY", dt)] = spy
        px[("LMT", dt)] = lmt
    trades = []
    n = 0
    d0 = date(2023, 1, 10)
    while d0 < date(2023, 8, 1):
        n += 1
        trades.append(
            TradeEvent(
                str(n), "ace", "LMT", d0, add_trading_days(d0, 5), "BUY", 50001, 100000
            )
        )
        n += 1
        trades.append(
            TradeEvent(
                str(n), "bob", "LMT", d0, add_trading_days(d0, 5), "BUY", 15001, 50000
            )
        )
        d0 += timedelta(days=21)
    return trades, securities, politicians, committees, PriceStore(px)


def test_run_backtest_ablations_public_metrics():
    trades, securities, politicians, committees, store = _tiny_walk_forward()
    zero = CostModel(commission_bps=0, half_spread_bps=0, impact_k=0)
    result = run_backtest(
        trades,
        securities,
        politicians,
        committees,
        store,
        start=date(2023, 6, 1),
        end=date(2023, 10, 31),
        execution_lag=1,
        cost_model=zero,
        run_ablations=True,
        ablation_seed=7,
    )
    assert set(result.ablations) == {"equal_skill", "no_delay_decay", "placebo_skill"}
    for name, row in result.ablations.items():
        assert row["strategy"] == "conviction"
        assert "sharpe" in row
        assert "cagr" in row
        assert "excess_cagr" in row
        assert "tstat_excess" in row
        assert "max_dd" in row
        assert isinstance(row["note"], str) and row["note"]
        assert isinstance(row["sharpe"], float)
        assert isinstance(row["cagr"], float)
