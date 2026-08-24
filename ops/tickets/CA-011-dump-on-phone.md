---
id: CA-011
title: Fixture dump on phone (RESEARCH FILE path)
priority: P1
status: ready
type: feature
effort: M
merge: auto
director_gate: false
blocked_by: []
---

# CA-011 Fixture dump on phone (RESEARCH FILE path)

## Why director
Director: eventually a real production app to trade on. Fake data forever is useless. Do not scrape House/Senate now. First prove the phone can show an ingested dump, still stamped not a live book, still not a broker.

## Why engine
`fetch`, `ingest`, and `run` exist. Default loop is `demo` (planted DGP). `make ingest-fixture` does not `run`. Leadership cannot screenshot real-shaped filings without a one-command path. No test that fixture ingest + run lights `mode=ingested` on `/api/dashboard`.

## Done when
- [ ] One documented command (Makefile or CLI) runs fixture ingest then `run` and writes `data/dashboard.json` with `mode=ingested`
- [ ] After that command, `/api/dashboard` and the phone banner are RESEARCH FILE, not SYNTHETIC DEMO
- [ ] Test uses recorded fixtures only (no live network)
- [ ] Watermark stays. No broker. No live-track-record copy

## Likely files
`Makefile`, `README.md`, `src/congress_alpha/cli.py`, `tests/test_api.py` or `tests/test_pipeline.py`

## Forbidden
- `trade_date` as event time
- claiming live track record on synthetic/ingested research
- scraping House Clerk / Senate eFD in this ticket
- AWS / S3
- brokerage / “place trade”

## Engineer prompt
Ticket CA-011. Wire a one-command fixture dump → ingest → run so the phone serves RESEARCH FILE. Tests on recorded fixtures, network off. Keep watermarks. Do not fetch live filings. Do not add a broker.
