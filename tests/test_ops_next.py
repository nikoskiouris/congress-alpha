from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ops_next", ROOT / "ops" / "next.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["ops_next"] = mod
SPEC.loader.exec_module(mod)

Ticket = mod.Ticket
next_id = mod.next_id
parse_frontmatter = mod.parse_frontmatter
pick = mod.pick
load_tickets = mod.load_tickets
parse_current = mod.parse_current


def test_frontmatter_lists_and_bools():
    text = """---
id: CA-009
title: x
director_gate: true
blocked_by: ["CA-002", "CA-003"]
---

body
"""
    fm = parse_frontmatter(text)
    assert fm["id"] == "CA-009"
    assert fm["director_gate"] is True
    assert fm["blocked_by"] == ["CA-002", "CA-003"]


def test_pick_skips_blocked_and_gate():
    tickets = [
        Ticket(id="CA-009", title="blocked", priority="P0", status="blocked", type="feature", effort="S"),
        Ticket(id="CA-010", title="gate", priority="P0", status="ready", type="feature", effort="S", director_gate=True),
        Ticket(id="CA-001", title="real", priority="P0", status="ready", type="feature", effort="M"),
        Ticket(id="CA-003", title="test", priority="P0", status="ready", type="test", effort="S"),
    ]
    chosen = pick(tickets, {"ticket": "none", "status": "idle"})
    assert chosen is not None
    assert chosen.id == "CA-001"


def test_pick_resumes_current():
    tickets = [
        Ticket(id="CA-001", title="a", priority="P0", status="ready", type="feature", effort="S"),
        Ticket(id="CA-002", title="b", priority="P0", status="in_progress", type="research", effort="L"),
    ]
    chosen = pick(tickets, {"ticket": "CA-002", "status": "in_progress"})
    assert chosen is not None and chosen.id == "CA-002"


def test_pick_respects_blocked_by():
    tickets = [
        Ticket(id="CA-001", title="a", priority="P0", status="ready", type="feature", effort="M"),
        Ticket(id="CA-009", title="b", priority="P0", status="ready", type="feature", effort="S", blocked_by=["CA-099"]),
    ]
    chosen = pick(tickets, {})
    assert chosen is not None and chosen.id == "CA-001"


def test_next_id_increments():
    tickets = [Ticket(id="CA-010", title="x")]
    assert next_id(tickets) == "CA-011"


def test_repo_board_has_seeded_tickets_and_a_legal_next():
    tickets = load_tickets()
    ids = {t.id for t in tickets}
    assert "CA-001" in ids
    current = parse_current()
    chosen = pick(tickets, current)
    if current.get("status") == "in_progress":
        assert chosen is not None
        return
    ready = [t for t in tickets if t.status not in {"blocked", "done", "discarded"} and not t.director_gate]
    if ready:
        assert chosen is not None
        assert chosen.status not in {"blocked", "done", "discarded"}
        assert chosen.director_gate is False
    else:
        assert chosen is None
