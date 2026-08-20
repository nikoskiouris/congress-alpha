#!/usr/bin/env python3
"""Pick the next GO ticket. Stdlib only. TPO runs this; Director never has to."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICKETS = ROOT / "ops" / "tickets"
CURRENT = ROOT / "ops" / "CURRENT.md"

PRIO_RANK = {"P0": 0, "P1": 10, "P2": 20, "P3": 30}
TYPE_RANK = {"feature": 0, "fix": 1, "research": 2, "test": 3, "chore": 4}
EFFORT_RANK = {"S": 0, "M": 1, "L": 4}
DONE = {"done", "discarded"}
SKIP = {"blocked", "done", "discarded"}


@dataclass
class Ticket:
    id: str
    title: str
    priority: str = "P2"
    status: str = "ready"
    type: str = "feature"
    effort: str = "M"
    merge: str = "auto"
    director_gate: bool = False
    blocked_by: list[str] = field(default_factory=list)
    path: str = ""

    @property
    def score(self) -> tuple:
        return (
            PRIO_RANK.get(self.priority, 25),
            TYPE_RANK.get(self.type, 5),
            EFFORT_RANK.get(self.effort, 2),
            self.id,
        )


def _coerce(raw: str):
    raw = raw.strip()
    if raw.lower() in {"true", "yes"}:
        return True
    if raw.lower() in {"false", "no"}:
        return False
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
    return raw.strip().strip("\"'")


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data: dict = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = _coerce(val)
    return data


def load_tickets(tickets_dir: Path = TICKETS) -> list[Ticket]:
    out: list[Ticket] = []
    if not tickets_dir.exists():
        return out
    for path in sorted(tickets_dir.glob("CA-*.md")):
        fm = parse_frontmatter(path.read_text())
        if not fm.get("id"):
            continue
        out.append(
            Ticket(
                id=str(fm["id"]),
                title=str(fm.get("title") or path.stem),
                priority=str(fm.get("priority") or "P2"),
                status=str(fm.get("status") or "ready"),
                type=str(fm.get("type") or "feature"),
                effort=str(fm.get("effort") or "M"),
                merge=str(fm.get("merge") or "auto"),
                director_gate=bool(fm.get("director_gate", False)),
                blocked_by=list(fm.get("blocked_by") or []),
                path=str(path.relative_to(ROOT)),
            )
        )
    return out


def parse_current(path: Path = CURRENT) -> dict:
    if not path.exists():
        return {"ticket": "none", "status": "idle"}
    data = {"ticket": "none", "status": "idle"}
    for line in path.read_text().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in {"ticket", "status", "branch", "started", "notes", "next"}:
            data[k] = v
    return data


def done_ids(tickets: list[Ticket]) -> set[str]:
    return {t.id for t in tickets if t.status in DONE}


def pick(tickets: list[Ticket], current: dict | None = None) -> Ticket | None:
    current = current or {}
    cid = str(current.get("ticket") or "none")
    by_id = {t.id: t for t in tickets}
    if cid in by_id and current.get("status") == "in_progress":
        t = by_id[cid]
        if t.status not in DONE:
            return t
    finished = done_ids(tickets)
    ready = []
    for t in tickets:
        if t.status in SKIP:
            continue
        if t.director_gate:
            continue
        if any(b not in finished for b in t.blocked_by):
            continue
        ready.append(t)
    if not ready:
        return None
    return sorted(ready, key=lambda x: x.score)[0]


def next_id(tickets: list[Ticket]) -> str:
    n = 0
    for t in tickets:
        m = re.match(r"CA-(\d+)$", t.id)
        if m:
            n = max(n, int(m.group(1)))
    return f"CA-{n + 1:03d}"


def brief_text(tickets: list[Ticket], current: dict, chosen: Ticket | None) -> str:
    open_n = sum(1 for t in tickets if t.status not in DONE)
    p0 = sum(1 for t in tickets if t.priority == "P0" and t.status not in SKIP)
    lines = [
        f"BOARD idle={current.get('status')} current={current.get('ticket', 'none')} open={open_n} p0_ready={p0}",
    ]
    if chosen:
        lines.append(
            f"NEXT {chosen.id} {chosen.priority} {chosen.type} {chosen.effort} merge={chosen.merge} :: {chosen.title}"
        )
        lines.append(f"TICKET {chosen.path}")
    else:
        lines.append("NEXT none — TPO must invent a ticket from ops/ROADMAP.md then build it.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Congress Alpha GO board")
    p.add_argument("--brief", action="store_true", help="short text for hooks / director")
    p.add_argument("--json", action="store_true", help="machine payload")
    p.add_argument("--list", action="store_true")
    args = p.parse_args(argv)
    tickets = load_tickets()
    current = parse_current()
    chosen = pick(tickets, current)
    if args.json:
        payload = {
            "current": current,
            "next": None if chosen is None else asdict(chosen),
            "next_new_id": next_id(tickets),
            "tickets": [asdict(t) for t in tickets],
        }
        print(json.dumps(payload, indent=2))
        return 0
    if args.list:
        for t in sorted(tickets, key=lambda x: x.score):
            print(f"{t.id:7} {t.priority} {t.status:11} {t.type:8} {t.effort}  {t.title}")
        return 0
    print(brief_text(tickets, current, chosen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
