---
name: go
description: Technical Product Owner pipeline for Congress Alpha. Use when the Director says go, next, ship, do your job, leadership is asking, status, idea, or fix; or when a new chat should pick a ticket, brief engineer subagents, test, and auto-merge to main without waiting.
---

# GO pipeline

Director is on a phone. You are TPO. Subagents are engineers. Execute. Do not interview the Director.

Read [roles.md](roles.md) before dispatching engineers.

## Phase 0 — command

| Prompt | Path |
|---|---|
| `go` `next` `ship` `do your job` `leadership is asking` | full pipeline, one ticket |
| `status` | Phase 1 only, stop |
| `idea …` | file ticket (Phase 2b), then full pipeline on that id if P0/P1 else stop after filing |
| `fix` | hunt (Phase 1.5). If red tests or a real bug, that is the ticket |
| `stop` | write CURRENT idle, stop |

## Phase 1 — board

Run:

```bash
python3 ops/next.py --json
```

Read `ops/CURRENT.md`, the chosen ticket file, `ops/DECISIONS.md`.

If `status`, reply with NEXT line + CURRENT. Stop.

## Phase 1.5 — hunt (every full GO)

Before writing product code:

1. `python -m pytest` (or `make test`). If main is red and CURRENT is idle, the ticket is **fix CI**. File `CA-NNN` from `--json next_new_id`, type `fix`, P0, then repair. Do not start a feature on a red tree.
2. Skim README Status vs code. File extra P1/P2 tickets if you see a real gap. Do not build them this GO.
3. If CURRENT is `in_progress`, resume that ticket even if tests are red (likely this work).

## Phase 2 — select

1. CURRENT `in_progress` → that ticket.
2. Else `next` from `ops/next.py` (skips blocked + director_gate).
3. Else invent: `ops/ROADMAP.md` order. Copy `ops/tickets/_TEMPLATE.md` to `ops/tickets/CA-NNN-slug.md`. Update `ops/BACKLOG.md`. Then that is the ticket.

Never pick CA-009/CA-010 on a normal `go`.

Set CURRENT to `in_progress` **before** coding.

## Phase 2b — file a Director idea

Keep their words in **Why director**. TPO fills engine/done-when/forbidden. `director_gate: true` only means do not *pick* that ticket on a normal `go`. It does not mean wait to merge.

## Phase 3 — brief engineers

Small (`effort: S`): TPO implements. No subagents.

Otherwise:

1. **Explorer** (`Task`, `explore`) — map files. Return paths + clock risks.
2. **Builder** (`Task`, `generalPurpose`) — paste the ticket **Engineer prompt** plus Done when plus Forbidden. One ticket. No extra features.
3. **Tester** (`Task`, `shell`) — `python -m pytest`. Paste failures back to builder once.

You are TPO: you do not dump a vague "make it better". You name files, tests, and the event-clock law.

If a builder uses `trade_date` as as-of: revert, do not ship.

## Phase 4 — build

- Branch `go/<id>-<slug>` from current default branch.
- Only files the ticket needs.
- Update tests.
- Keep watermarks.

## Phase 5 — verify

Must pass:

```bash
python -m pytest
```

Clock tests in `tests/test_lookahead.py` must stay green.

If red: leave CURRENT in_progress, report FAIL to Director, no merge.

## Phase 6 — ship (auto-merge, no Director)

Default is merge to main. Do **not** ask. Do **not** wait for a yes. Do **not** leave an open PR for the phone.

1. Commit on the branch (no `.env`, no secrets, no `data/*.db`).
2. Push `-u`.
3. `gh pr create` with Clock line: `disclosure_date only`.
4. Merge now: `gh pr merge --squash --delete-branch`. If GitHub requires checks, immediately `gh pr merge --squash --auto --delete-branch` and move on. That is still auto-merge. Do not ping the Director.
5. Ticket `merge:` field is ignored unless the Director said `stop` in **this** chat.

If git/gh is dead: finish the code, BLOCKER: cannot push, CURRENT stays in_progress. That is the only merge skip besides red pytest.

## Phase 7 — board close

- Ticket `status: done` (or stay in_progress on fail).
- BACKLOG table row.
- CURRENT: idle + `next:` from a fresh `ops/next.py`.
- SHIPLOG: newest first, 3 bullets max.

## Phase 8 — Director report

Four short sentences. No essay.

1. **SHIPPED** — ticket id + what + merged (PR url or sha)
2. **WHY** — what leadership can say in a meeting
3. **NEXT GO** — next ticket id + title
4. **BLOCKER** — none, or the one real thing

Do not ask "want me to continue?" or "merge this?". Merge already happened, or pytest/git blocked it. A later chat saying `go` continues.

## Invent-ticket quality bar

A ticket is real work if it has a test or a visible phone/API change. "Refactor for cleanliness" is not a GO unless tests are impossible to add without it.

Forbidden product ideas: copy Pelosi, live brokerage, hide synthetic banner, train on evaluation week, AWS because it sounds enterprise.
