#!/usr/bin/env python3
"""sessionStart: inject GO board so a new chat can type go."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _brief() -> str:
    script = ROOT / "ops" / "next.py"
    if not script.exists():
        return "BOARD missing ops/next.py"
    try:
        out = subprocess.check_output(
            [sys.executable, str(script), "--brief"],
            cwd=str(ROOT),
            text=True,
            timeout=12,
        )
        return out.strip()
    except Exception as exc:  # fail open
        return f"BOARD unread ({exc})"


def main() -> int:
    _ = sys.stdin.read()
    ctx = (
        "GO PIPELINE. You are Technical Product Owner. Director is on a phone.\n"
        "If this prompt is go/next/ship/do your job/leadership is asking: "
        "read .cursor/skills/go/SKILL.md and execute. Do not ask what to work on.\n"
        "AUTO-MERGE: pytest green → commit, push, PR, merge to main. Do not wait for Director.\n"
        "status = board only. idea = file ticket then maybe GO.\n"
        f"{_brief()}\n"
    )
    sys.stdout.write(json.dumps({"additional_context": ctx}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
