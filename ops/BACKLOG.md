# Backlog

Source of truth is `ops/tickets/CA-*.md` plus `python3 ops/next.py`.
This table is the director view. TPO updates it when status changes.

| ID | P | Status | Type | Effort | Title |
|---|---|---|---|---|---|
| CA-001 | P0 | done | feature | M | Phone ingest-health card |
| CA-002 | P0 | done | research | L | Watcher dump fetch + manifest |
| CA-003 | P0 | done | test | S | API watermark tests |
| CA-004 | P1 | ready | feature | M | Ingest hygiene in research brief |
| CA-005 | P1 | ready | research | M | Extra falsification ablations |
| CA-006 | P1 | done | feature | S | WHY panel already-moved % |
| CA-007 | P2 | ready | chore | S | Makefile run + ruff extra |
| CA-008 | P2 | ready | test | M | Price holes do not invent returns |
| CA-009 | P3 | blocked | research | L | Official Clerk/eFD parse |
| CA-010 | P3 | blocked | research | L | ML estimators (same clock) |

Pick rule: resume CURRENT if `in_progress`, else `ops/next.py` (P0 feature before tests, skip blocked and director_gate).
