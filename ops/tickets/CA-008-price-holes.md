---
id: CA-008
title: Price holes do not invent returns
priority: P1
status: ready
type: test
effort: M
merge: auto
director_gate: false
blocked_by: []
---

# CA-008 Price holes do not invent returns

## Why director
Bad prices create fake alpha. Leadership would treat it as a finding.

## Why engine
`PriceStore` joins adj-close. Missing sessions / missing SPY need tests: skip or explicit None, never silent 0 that looks like a flat name.

## Done when
- [ ] Tests: missing ticker, missing day, missing SPY → excess/holding return is None or skipped, not 0-by-accident
- [ ] Event study / skill fit skip incomplete windows
- [ ] Short comment in `prices.py` stating the rule

## Likely files
`src/congress_alpha/prices.py`, `tests/test_metrics.py` or new `tests/test_prices.py`, maybe `skill.py`

## Forbidden
- forward-filling across a halt in a way that creates a return
- using trade_date as the return start

## Engineer prompt
Lock price-hole behavior with tests. Incomplete windows do not become 0% skill. Keep disclosure clock.
