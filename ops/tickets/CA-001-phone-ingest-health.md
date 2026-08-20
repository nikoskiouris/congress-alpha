---
id: CA-001
title: Phone ingest-health card
priority: P0
status: done
type: feature
effort: M
merge: auto
director_gate: false
blocked_by: []
---

# CA-001 Phone ingest-health card

## Why director
Leadership will screenshot the phone demo and ask if the data is real. Home screen must show ingest counts or "synthetic — no filings".

## Why engine
`data/ingest_report.json` exists after ingest and is gitignored. API/UI never show n_read / n_rejected / top reasons. Demo looks like a live book.

## Done when
- [x] `GET /api/ingest` returns `{mode, n_read, n_accepted, n_rejected, reasons[]}` and synthetic demo returns zeros + `mode=synthetic`
- [x] Phone home has a small INGEST card under the banner
- [x] Tests cover synthetic vs a fixture ingest report
- [x] Banner text still says SYNTHETIC DEMO or RESEARCH FILE

## Likely files
`src/congress_alpha/api.py`, `frontend/index.html`, `src/congress_alpha/pipeline.py`, `tests/test_api.py` (new ok)

## Forbidden
- claiming live track record
- using trade_date as event time
- pulling real network filings in this ticket

## Engineer prompt
Add `/api/ingest` and a phone INGEST card. Synthetic path: no file → n_read=0, note="synthetic DGP". If `data/ingest_report.json` exists, surface counts and top reject reasons. Tests with httpx. Do not change the event clock.
