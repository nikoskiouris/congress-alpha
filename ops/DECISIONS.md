# Decisions

## D1 — Event clock
`disclosure_date` is the only legal event time. `trade_date` is a feature (lag, already-moved). Never fill, train, or backtest as-of `trade_date`.

## D2 — Demo honesty
Synthetic DGP and ingested research files are not a live track record. UI, API, brief must watermark. If a GO would make the demo look live, kill the GO.

## D3 — Estimators wait
No ML / AWS until years of clean point-in-time filings exist (`spec/MODEL.md` §9–10). Tickets CA-009+ stay blocked.

## D4 — GO ships one ticket
One ticket per `go`. Resume CURRENT if in_progress. Tests must pass or the ticket stays open. Passing tests auto-merge. Do not wait.

## D5 — Auto-merge (do not wait)
`go` auto-merges to main. Pytest green → commit, push, PR, squash-merge. Never ask the Director. Never wait for approval.
If GitHub requires CI, enable auto-merge on the PR and continue. Do not ping.
Skip merge only if pytest is red, git/gh is dead, or Director said `stop` in this chat.
`director_gate: true` means do not pick that ticket on a normal `go`. It is not a merge hold.
