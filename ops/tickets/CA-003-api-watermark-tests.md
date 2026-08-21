---
id: CA-003
title: API watermark tests
priority: P0
status: done
type: test
effort: S
merge: auto
director_gate: false
blocked_by: []
---

# CA-003 API watermark tests

## Why director
If `/api/health` or `/api/brief` ever omit `synthetic`, someone will paste numbers into a deck as live alpha.

## Why engine
`api.py` already returns mode. No tests. Easy to regress.

## Done when
- [x] Tests hit `/api/health`, `/api/brief`, `/api/dashboard` with a temp dashboard.json
- [x] `mode=synthetic` required; brief payload not empty
- [x] A dashboard missing `mode` still reports synthetic (current health fallback)

## Likely files
`tests/test_api.py`, `src/congress_alpha/api.py` only if fallback is broken

## Forbidden
- deleting the synthetic fallback
- treating ingested mode as live

## Engineer prompt
Add httpx/FastAPI tests for watermark/mode on health, brief, dashboard. Use tmp dashboard files. Keep existing fallback: missing mode → synthetic.
