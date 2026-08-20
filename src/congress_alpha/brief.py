"""Leadership research memo from a dashboard payload.

Plain language. Disclosure clock only. Not a live track record.
"""

from __future__ import annotations

from pathlib import Path

BOOK_ORDER = ("conviction", "consensus", "momentum", "spy")
ABLATION_ORDER = ("equal_skill", "no_delay_decay", "placebo_skill")


def _num(x, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    try:
        if x != x:  # nan
            return "n/a"
    except Exception:
        return "n/a"
    return f"{float(x):.{digits}f}"


def _pct(x, digits: int = 1) -> str:
    if x is None:
        return "n/a"
    try:
        if x != x:
            return "n/a"
    except Exception:
        return "n/a"
    return f"{float(x) * 100:.{digits}f}%"


def _walk(d: dict, *keys) -> dict:
    cur: object = d
    for k in keys:
        if not isinstance(cur, dict):
            return {}
        if k in cur:
            cur = cur[k]
            continue
        if isinstance(k, str) and k.isdigit() and int(k) in cur:
            cur = cur[int(k)]
            continue
        if str(k) in cur:
            cur = cur[str(k)]
            continue
        return {}
    return cur if isinstance(cur, dict) else {}


def _classification(mode: str) -> tuple[str, str]:
    if mode == "ingested":
        label = "INGESTED RESEARCH FILE"
        watermark = (
            "THESE NUMBERS ARE NOT A LIVE TRACK RECORD. This is a research file "
            "built from ingested disclosures on the DISCLOSURE clock. It is not "
            "audited performance, not a live book, and not a claim that live "
            "congressional alpha has been measured."
        )
    else:
        label = "SYNTHETIC DEMO"
        watermark = (
            "THESE NUMBERS ARE NOT A LIVE TRACK RECORD. This memo is the output "
            "of a planted synthetic Congress (fictional names, planted skill). "
            "It is not live congressional alpha, not a composite, and not a "
            "number that can be allocated to."
        )
    return label, watermark


def _metric_rows(metrics: dict) -> list[str]:
    names = [n for n in BOOK_ORDER if n in metrics]
    names += [n for n in metrics if n not in names]
    lines = [
        "| Book | CAGR | Excess | Sharpe | t-stat | Max DD | DSR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        m = metrics.get(name) or {}
        lines.append(
            f"| {name} | {_pct(m.get('cagr'))} | {_pct(m.get('excess_cagr'))} | "
            f"{_num(m.get('sharpe'), 2)} | {_num(m.get('tstat_excess'), 2)} | "
            f"{_pct(m.get('max_dd'))} | {_num(m.get('deflated_sharpe'), 2)} |"
        )
    if len(lines) == 2:
        lines.append("| — | n/a | n/a | n/a | n/a | n/a | n/a |")
    return lines


def _ablation_rows(ablations: dict) -> list[str]:
    names = [n for n in ABLATION_ORDER if n in ablations]
    names += [n for n in ablations if n not in names]
    lines = [
        "| Ablation | Strategy | CAGR | Excess | Sharpe | t-stat | Max DD |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    if not names:
        lines.append("| none in payload | — | n/a | n/a | n/a | n/a | n/a |")
        return lines
    for name in names:
        row = ablations.get(name) or {}
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {name} | {row.get('strategy') or '—'} | {_pct(row.get('cagr'))} | "
            f"{_pct(row.get('excess_cagr'))} | {_num(row.get('sharpe'), 2)} | "
            f"{_num(row.get('tstat_excess'), 2)} | {_pct(row.get('max_dd'))} |"
        )
    return lines


def _ablation_notes(ablations: dict, metrics: dict) -> list[str]:
    conv = (metrics.get("conviction") or {}).get("sharpe")
    eq = (ablations.get("equal_skill") or {}).get("sharpe") if isinstance(ablations.get("equal_skill"), dict) else None
    plc = (ablations.get("placebo_skill") or {}).get("sharpe") if isinstance(ablations.get("placebo_skill"), dict) else None
    bullets = [
        "- If equal_skill Sharpe is close to conviction, skill ranking may not be doing work.",
        "- placebo_skill should be weaker than conviction if planted or real skill exists.",
    ]
    if conv is not None and eq is not None:
        try:
            gap = abs(float(eq) - float(conv))
        except (TypeError, ValueError):
            gap = None
        if gap is not None and gap < 0.15:
            bullets.append(
                f"- Observed: equal_skill Sharpe {_num(eq)} vs conviction {_num(conv)} "
                f"(gap {gap:.2f}). Skill ranking may not be doing work."
            )
        elif gap is not None:
            bullets.append(
                f"- Observed: equal_skill Sharpe {_num(eq)} vs conviction {_num(conv)} "
                f"(gap {gap:.2f}). Ranking is moving the book."
            )
    if conv is not None and plc is not None:
        try:
            weaker = float(plc) < float(conv)
        except (TypeError, ValueError):
            weaker = None
        if weaker is True:
            bullets.append(
                f"- Observed: placebo_skill Sharpe {_num(plc)} is weaker than conviction "
                f"{_num(conv)}, consistent with planted or real skill."
            )
        elif weaker is False:
            bullets.append(
                f"- Observed: placebo_skill Sharpe {_num(plc)} is not weaker than conviction "
                f"{_num(conv)}. Treat skill as unproven."
            )
    for name, row in ablations.items():
        if isinstance(row, dict) and row.get("note"):
            bullets.append(f"- {name}: {row['note']}")
    return bullets


def _event_line(label: str, cell: dict) -> str:
    if not cell:
        return f"- {label}: not in payload"
    return (
        f"- {label}: mean {_pct(cell.get('mean'))}  t={_num(cell.get('tstat'), 2)}  "
        f"n={cell.get('n', 'n/a')}  hit={_pct(cell.get('hit'))}"
    )


def render_brief(payload: dict) -> str:
    mode = str(payload.get("mode") or "synthetic")
    label, watermark = _classification(mode)
    metrics = payload.get("metrics") or {}
    ablations = payload.get("ablations") or {}
    leakage = payload.get("leakage") or (payload.get("execution") or {}).get("leakage") or {}
    es = payload.get("event_study") or {}
    execution = payload.get("execution") or {}
    as_of = payload.get("as_of") or "n/a"
    disclaimer = str(payload.get("disclaimer") or "").strip() or (
        "Not investment advice. Signals use disclosure_date; trade_date never."
    )

    all20 = _walk(es, "by_horizon", "20")
    skilled20 = _walk(es, "by_skill", "skilled", "20")

    lines: list[str] = [
        "# CONGRESS ALPHA — RESEARCH BRIEF",
        "",
        "## Classification",
        "",
        f"**{label}**",
        "",
        watermark,
        "",
        f"Mode: `{mode}`",
        f"As of: {as_of}",
        f"Execution lag: {execution.get('lag_sessions', 'n/a')} session(s)",
        f"Cost model: {execution.get('cost_model') or 'default'}",
        "",
        "## Product statement",
        "",
        "The model answers one question:",
        "",
        "> Which publicly disclosed congressional trades historically contain useful "
        "information after reporting delay, politician skill, industry expertise, "
        "trade size, consensus, and already-happened price moves?",
        "",
        "That is post-disclosure information after delay, skill, size, consensus, "
        "and moves that have already happened. The engine never pretends it could "
        "have bought on the private trade date.",
        "",
        "## Clock rules",
        "",
        "disclosure_date is the only legal event time; trade_date never.",
        "",
        "| Clock | Allowed |",
        "|---|---|",
        "| disclosure_date | yes |",
        "| disclosure_date + horizon for labels (window closed) | yes |",
        "| trade_date | never |",
        "",
        "Senate/House PTRs can legally arrive 30/45 days late. A June 1 NVDA buy "
        "disclosed July 10 is tradable (or not) on July 10, not June 1.",
        "",
        "## Headline walk-forward metrics",
        "",
        "Next-session fill, costs on, DISCLOSURE clock only. Books: conviction, "
        "consensus, momentum, spy (if present).",
        "",
    ]
    lines.extend(_metric_rows(metrics))
    lines.extend(
        [
            "",
            "## Ablations",
            "",
            "Same walk-forward, one knob removed at a time. Read against conviction.",
            "",
        ]
    )
    lines.extend(_ablation_rows(ablations))
    lines.append("")
    lines.append("Interpretation:")
    lines.extend(_ablation_notes(ablations, metrics))
    lines.extend(
        [
            "",
            "## Leakage audit",
            "",
            "These counts exist so a reader can see the DISCLOSURE clock working.",
            "",
            f"- trades: {leakage.get('n_trades', 'n/a')}",
            f"- delayed filings (trade_date before disclosure_date): {leakage.get('n_with_reporting_delay', 'n/a')}",
            f"- trade_date traps still private at last as_of: {leakage.get('n_trade_date_traps_at_last_as_of', 'n/a')}",
            f"- disclosures after last as_of: {leakage.get('n_disclosures_after_last_as_of', 'n/a')}",
            f"- note: {leakage.get('note') or 'trade_date is not an event time.'}",
            "",
            "## Event study (20d, post-disclosure vs SPY)",
            "",
            "CARs start the next session after disclosure_date. Skill buckets use "
            "the last weight known strictly before that date.",
            "",
            _event_line("all 20d", all20),
            _event_line("skilled 20d", skilled20),
            "",
            "## What this does NOT claim",
            "",
            "- Not investment advice and not a recommendation to buy or sell anything.",
            "- Not a Pelosi-copy product and not a celebrity-trader feed.",
            "- Not live AUM, not a live track record, and not a number that can be allocated to.",
            "- Demo numbers are a planted data-generating process unless this file is ingested research.",
            "",
            "## What's next",
            "",
            "- Drop official PTR JSON and adj-close CSV into ingest "
            "(`python -m congress_alpha ingest`, then `python -m congress_alpha run`).",
            "- No ML until clean point-in-time years exist.",
            "- No AWS required for research.",
            "",
            "## Disclaimer",
            "",
            disclaimer,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_brief(payload: dict, path: Path) -> Path:
    """Write a deterministic leadership memo. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_brief(payload))
    return path
