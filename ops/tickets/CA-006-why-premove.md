---
id: CA-006
title: WHY panel already-moved percent
priority: P1
status: ready
type: feature
effort: S
merge: auto
director_gate: false
blocked_by: []
---

# CA-006 WHY panel already-moved percent

## Why director
Phone WHY screen must answer "did this name already move before the filing?" in one number.

## Why engine
`explain.py` has positives/negatives text. PremoveDecay is in the formula, not a first-class WHY field.

## Done when
- [ ] WHY JSON includes `premove_pct` (or similar) for the ticker
- [ ] Phone WHY card shows it
- [ ] Test on toy universe

## Likely files
`src/congress_alpha/explain.py`, `frontend/index.html`, `tests/` (portfolio or new)

## Forbidden
- using pre-disclosure price path from trade_date as the event
- implying committee star = insider edge

## Engineer prompt
Expose already-moved / premove decay on WHY payload and the phone WHY view. Keep committee star as display-only.
