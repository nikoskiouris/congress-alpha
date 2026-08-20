---
id: CA-002
title: Watcher dump fetch + manifest
priority: P0
status: ready
type: research
effort: L
merge: auto
director_gate: false
blocked_by: []
---

# CA-002 Watcher dump fetch + manifest

## Why director
Rollout needs a path off the planted DGP. Leadership keeps asking when live filings land. This is the on-ramp, still not a live book.

## Why engine
`congress_alpha.ingest` reads local watcher JSON. No fetch, no manifest, no recorded as-of. Easy to mix transaction_date into the clock.

## Done when
- [ ] CLI `python -m congress_alpha fetch --source house-watcher --out data/raw/` (or senate-watcher) writes files + `manifest.json` with fetched_at, source URL, sha256
- [ ] Ingest still keyed on `disclosure_date`; fetch must not rename that field to trade_date
- [ ] Test uses a tiny recorded fixture, not a live network call in CI
- [ ] README one-liner: convenience dump, House Clerk / Senate eFD remain legal source
- [ ] Output still watermarked RESEARCH FILE after `run`

## Likely files
`src/congress_alpha/cli.py`, new `src/congress_alpha/fetch.py`, `tests/test_fetch.py`, `README.md`

## Forbidden
- training or filling on trade_date
- scraping that dumps options into accepted trades
- calling this a live track record
- AWS

## Engineer prompt
Add an optional fetch for community House/Senate stock-watcher JSON into `data/raw/` with a manifest. CI tests a recorded mini fixture, network off. Keep ingest reject rules. Document legal source vs convenience dump.
