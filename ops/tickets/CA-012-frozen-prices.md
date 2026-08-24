---
id: CA-012
title: Frozen adj-close snapshot for dump tickers
priority: P1
status: ready
type: research
effort: L
merge: auto
director_gate: false
blocked_by: ["CA-011"]
---

# CA-012 Frozen adj-close snapshot for dump tickers

## Why director
Director wants real filings on the path to a tradable research app. Watcher JSON alone cannot run. We need frozen prices, not a scrape on every page load. Do not build S3. Do not scrape Clerk/eFD in this ticket.

## Why engine
`ingest` requires `--prices` CSV. `fetch` only writes watcher JSON. There is no recorded as-of price snapshot + manifest. Live Yahoo inside the backtest is look-ahead. Missing sessions must not become 0% returns (see CA-008).

## Done when
- [ ] CLI writes adj-close CSV + `manifest.json` (`fetched_at`, source, sha256) for tickers in a trades file
- [ ] Bytes frozen as received; job does not rename `disclosure_date` or fill on `trade_date`
- [ ] CI test uses a tiny recorded fixture, no live network
- [ ] README: convenience prices, not a live book; warehouse stays SQLite
- [ ] After ingest+run, output still watermarked RESEARCH FILE

## Likely files
`src/congress_alpha/cli.py`, new `src/congress_alpha/prices_fetch.py` (or extend `fetch.py`), `tests/test_fetch.py` or new test, `README.md`

## Forbidden
- `trade_date` as event time
- claiming live track record
- scraping House Clerk / Senate eFD
- AWS / S3 as the hot store
- pulling live prices inside pytest
- brokerage

## Engineer prompt
Ticket CA-012. Add frozen adj-close snapshot fetch for tickers listed in a dump, with a manifest, same honesty as watcher fetch. CI uses a recorded mini fixture, network off. SQLite warehouse. disclosure_date remains event time. Do not add AWS.
