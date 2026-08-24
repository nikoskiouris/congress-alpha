---
id: CA-006
title: WHY panel already-moved percent
priority: P2
status: done
type: feature
effort: S
merge: auto
director_gate: false
blocked_by: []
---

# CA-006 WHY panel already-moved percent

## Why director
Phone WHY screen must answer "did this name already move before the filing?" in one number. Demoted behind the real-dump on-ramp: Director wants frozen filings before more fake-demo chrome.

## Why engine
`explain.py` has positives/negatives text. PremoveDecay is in the formula, not a first-class WHY field.

## Done when
- [x] WHY JSON includes `premove_pct` (or similar) for the ticker
- [x] Phone WHY card shows it
- [x] Test on toy universe

## Likely files
`src/congress_alpha/explain.py`, `frontend/index.html`, `tests/` (portfolio or new)

## Forbidden
- using pre-disclosure price path from trade_date as the event
- implying committee star = insider edge

## Engineer prompt
Expose already-moved / premove decay on WHY payload and the phone WHY view. Keep committee star as display-only.
