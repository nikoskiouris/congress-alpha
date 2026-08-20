---
id: CA-007
title: Makefile run + ruff extra
priority: P2
status: ready
type: chore
effort: S
merge: auto
director_gate: false
blocked_by: []
---

# CA-007 Makefile run + ruff extra

## Why director
Small. Only if no P0/P1 ready. Makes phone-driven agents less clumsy.

## Why engine
Makefile has demo/test/serve/brief/ingest-fixture. No `run`. No optional ruff.

## Done when
- [ ] `make run` documented, points at ingested db
- [ ] optional `[dev]` extra or docs for ruff; do not fail CI on ruff unless already clean
- [ ] no behavior change to the model

## Likely files
`Makefile`, `pyproject.toml`, `README.md`

## Forbidden
- adding AWS
- reformatting the whole repo as the ticket

## Engineer prompt
Add `make run`. Optional ruff extra. Do not mass-format. Do not touch formulas.
