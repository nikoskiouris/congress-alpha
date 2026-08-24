# Ship log

Newest first. One block per GO.

## 2026-08-24 — board: real-dump on-ramp

- Director wants a path to a tradable research app. Fake DGP forever is out. No scrape this chat. No broker.
- New CA-011 (fixture dump on phone) and CA-012 (frozen prices). CA-006 demoted. CA-008 promoted. CA-009 still gated.
- Next GO is CA-004 ingest hygiene in the research brief.

## 2026-08-20 — CA-003 API watermark tests

- `/api/health`, `/api/brief`, `/api/dashboard` tests on a temp dashboard.json.
- Missing `mode` still reports synthetic. Ingested is not live.
- Next GO is CA-004 ingest hygiene in the research brief.

## 2026-08-20 — CA-002 watcher dump fetch

- CLI `fetch` writes community watcher JSON + `manifest.json` (fetched_at, url, sha256).
- Dump bytes unchanged; `disclosure_date` not renamed. Still RESEARCH FILE after `run`.
- Next GO is CA-003 API watermark tests.

## 2026-08-20 — CA-001 phone ingest-health

- `GET /api/ingest` plus phone INGEST card: counts or “synthetic — no filings”.
- Banner still SYNTHETIC DEMO / RESEARCH FILE. Not a live book.
- Next GO is CA-002 watcher dump fetch + manifest.

## 2026-08-20 — pipeline stand-up (ops)

- Board, GO skill, TPO rules, session brief hook.
- No product code. Next GO is CA-001.
