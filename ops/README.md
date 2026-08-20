# Ops board

Director (phone) types `go`. Technical Product Owner reads this folder, ships **one** ticket, and auto-merges. Do not wait.

| File | Job |
|---|---|
| CURRENT.md | in-flight ticket or idle |
| BACKLOG.md | director table |
| tickets/CA-*.md | the actual work |
| ROADMAP.md | what to invent when the board is empty |
| DECISIONS.md | laws |
| SHIPLOG.md | what already shipped |
| next.py | pick next ticket |

```bash
python3 ops/next.py          # NEXT line
python3 ops/next.py --list
python3 ops/next.py --json
```

TPO never codes without a ticket. Empty board → file a ticket from ROADMAP, then build it.
