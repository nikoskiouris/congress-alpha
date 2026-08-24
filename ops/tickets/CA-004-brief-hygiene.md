---
id: CA-004
title: Ingest hygiene in research brief
priority: P1
status: done
type: feature
effort: M
merge: auto
director_gate: false
blocked_by: []
---

# CA-004 Ingest hygiene in research brief

## Why director
The memo leadership reads has metrics and ablations. It does not say how dirty the file was. They will ask "did we drop the junk?"

## Why engine
`brief.py` has no ingest section. `IngestReport` is not copied into `dashboard.json`.

## Done when
- [x] `dashboard.json` includes `ingest` summary when ingest ran; synthetic demo has `ingest: {mode: synthetic, n_read: 0}`
- [x] `data/research_brief.md` has a DATA HYGIENE section (accepted/rejected/top reasons)
- [x] Test on a fake payload

## Likely files
`src/congress_alpha/brief.py`, `src/congress_alpha/pipeline.py`, `tests/test_brief.py`

## Forbidden
- presenting reject rates as alpha
- silent-defaulting amount bands

## Engineer prompt
Persist ingest summary on dashboard payload. Render DATA HYGIENE in the research brief. Synthetic demo must still scream not-live.
