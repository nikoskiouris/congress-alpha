"""Falsification ablations for the conviction book.

Shadow books reuse a fitted SkillBook (no refit) on the same disclosure_date
clock. They exist to answer: does politician skill actually matter, or are we
just copying Congress?
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from congress_alpha.skill import SkillBook

EQUAL_SKILL_WEIGHT = 0.40

ABLATION_NAMES = ("equal_skill", "no_delay_decay", "placebo_skill")

ABLATION_NOTES = {
    "equal_skill": (
        "All politicians get identical weight. Tests whether skill ranking matters."
    ),
    "no_delay_decay": (
        "Delay decay disabled (all lag buckets=1). Tests whether reporting lag is priced."
    ),
    "placebo_skill": (
        "Permute w_p across politicians each week. Should destroy planted skill."
    ),
}


def equal_skill_book(book: SkillBook) -> SkillBook:
    """Copy of `book` with every politician / sector weight set to 0.40."""
    return replace(
        book,
        overall={pid: EQUAL_SKILL_WEIGHT for pid in book.overall},
        sector={k: EQUAL_SKILL_WEIGHT for k in book.sector},
    )


def no_delay_book(book: SkillBook) -> SkillBook:
    """Copy of `book` with every delay-remaining bucket forced to 1.0."""
    return replace(
        book,
        delay_remaining={k: 1.0 for k in book.delay_remaining},
    )


def permute_skill_book(book: SkillBook, rng: np.random.Generator) -> SkillBook:
    """Permutation placebo: reassign overall (and sector) weights across politician ids.

    Sector names stay attached to the weight; only the politician id is shuffled.
    Delay / premove fields are left unchanged.
    """
    pids = list(book.overall.keys())
    if not pids:
        return replace(book, overall=dict(book.overall), sector=dict(book.sector))

    order = rng.permutation(len(pids))
    new_overall = {
        pids[i]: book.overall[pids[int(order[i])]] for i in range(len(pids))
    }

    # Same identity permutation: dest pids[i] receives src pids[order[i]]'s sector map.
    new_sector: dict[tuple[str, str], float] = {}
    for i, dest in enumerate(pids):
        src = pids[int(order[i])]
        for (pid, sec), weight in book.sector.items():
            if pid == src:
                new_sector[(dest, sec)] = weight
    return replace(book, overall=new_overall, sector=new_sector)


def ablation_public(name: str, strategy_result) -> dict:
    """Pack walk-forward metrics plus the leadership-facing note for `name`."""
    stats = strategy_result.stats
    return {
        "strategy": "conviction",
        "cagr": float(strategy_result.cagr),
        "excess_cagr": float(strategy_result.excess_cagr),
        "sharpe": float(strategy_result.sharpe),
        "tstat_excess": float(stats.tstat_excess),
        "max_dd": float(strategy_result.max_dd),
        "note": ABLATION_NOTES[name],
    }
