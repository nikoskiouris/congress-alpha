---
id: CA-010
title: ML estimators on the same clock
priority: P3
status: blocked
type: research
effort: L
merge: auto
director_gate: true
blocked_by: ["CA-002", "CA-009"]
---

# CA-010 ML estimators (same clock)

## Why director
Cool later. Not a rollout feature. MODEL.md says wait for years of PIT.

## Why engine
V1 is tanh shrinkage. Replacing it without PIT data is theater.

## Done when
- [ ] Same labels, same walk-forward, same ban on trade_date event time
- [ ] Nested as-of still holds

## Forbidden
- picking this on a normal `go`
- training on the evaluation week

## Engineer prompt
Do not implement on `go`. Unblock only after Stage C.
