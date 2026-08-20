---
id: CA-005
title: Extra falsification ablations
priority: P1
status: ready
type: research
effort: M
merge: auto
director_gate: false
blocked_by: []
---

# CA-005 Extra falsification ablations

## Why director
If placebo still looks good, we cannot tell leadership skill is a finding. Need more ways to kill the book.

## Why engine
Have equal_skill, no_delay_decay, placebo_skill. Missing: no_life, no_premove. A disclosure-date shuffle that should destroy PIT skill.

## Done when
- [ ] Two new ablations wired into demo/run like the existing three
- [ ] Tests assert they run and return sharpe keys
- [ ] Brief table includes them
- [ ] If a new placebo beats conviction on synthetic DGP, comment in brief interpretation — do not hide it

## Likely files
`src/congress_alpha/ablation.py`, `src/congress_alpha/backtest.py`, `tests/test_ablation.py`, `src/congress_alpha/brief.py`

## Forbidden
- measuring skill from trade_date
- dropping the existing placebo_skill

## Engineer prompt
Add no_life and no_premove ablations (weights of 1 / skip already-moved penalty). Keep the same walk-forward. Tests + brief rows. Do not add ML.
