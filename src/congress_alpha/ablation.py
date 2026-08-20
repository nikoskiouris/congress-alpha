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

    def remap_pid(src: dict) -> dict:
        out = {}
        for i, dest in enumerate(pids):
            donor = pids[int(order[i])]
            if donor in src:
                out[dest] = src[donor]
        return out

    def remap_pid_sector(src: dict) -> dict:
        out = {}
        for i, dest in enumerate(pids):
            donor = pids[int(order[i])]
            for (pid, sec), val in src.items():
                if pid == donor:
                    out[(dest, sec)] = val
        return out

    return replace(
        book,
        overall=remap_pid(book.overall),
        sector=remap_pid_sector(book.sector),
        sample_n=remap_pid(book.sample_n),
        sector_n=remap_pid_sector(book.sector_n),
        overall_alpha=remap_pid(book.overall_alpha),
        sector_alpha=remap_pid_sector(book.sector_alpha),
        hit_rate=remap_pid(book.hit_rate),
        premove_share=remap_pid(book.premove_share),
    )


def ablation_public(name: str, strategy_result) -> dict:
    """Pack walk-forward metrics plus the leadership-facing note for `name`."""
    stats = strategy_result.stats
    return {
        "strategy": "conviction",
        "cagr": round(float(strategy_result.cagr), 4),
        "excess_cagr": round(float(strategy_result.excess_cagr), 4),
        "sharpe": round(float(strategy_result.sharpe), 3),
        "tstat_excess": round(float(stats.tstat_excess), 2),
        "max_dd": round(float(strategy_result.max_dd), 4),
        "note": ABLATION_NOTES[name],
    }
