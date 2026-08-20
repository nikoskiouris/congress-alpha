from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print_metrics(payload: dict) -> None:
    print(f"as_of {payload['as_of']}  congress score {payload['score']} {payload['label']}")
    print()
    print(f"{'strategy':12} {'cagr':>8} {'excess':>8} {'sharpe':>7} {'maxdd':>8} {'hit':>6}")
    for name, m in payload["metrics"].items():
        print(
            f"{name:12} {m['cagr']:8.1%} {m['excess_cagr']:8.1%} "
            f"{m['sharpe']:7.2f} {m['max_dd']:8.1%} {m['hit_weeks']:6.1%}"
        )
    print()
    print("top signals")
    for row in payload.get("top_signals", [])[:6]:
        print(f"  {row['ticker']:6} {row['score']:3}  n={row['n_politicians']}")


def _print_ablations(ablations: dict) -> None:
    if not ablations:
        return
    print()
    print("ABLATIONS")
    print(f"{'name':16} {'sharpe':>7} {'excess':>8}")
    for name, row in ablations.items():
        if not isinstance(row, dict):
            continue
        sh = row.get("sharpe")
        ex = row.get("excess_cagr")
        sh_s = f"{float(sh):7.2f}" if isinstance(sh, (int, float)) else f"{'n/a':>7}"
        ex_s = f"{float(ex):8.1%}" if isinstance(ex, (int, float)) else f"{'n/a':>8}"
        print(f"{name:16} {sh_s} {ex_s}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="congress-alpha",
        description="Congressional Trading Factor Model (event-time)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="Generate synthetic data, backtest, write dashboard")
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--db", type=Path, default=Path("data/congress_alpha.db"))

    serve = sub.add_parser("serve", help="Serve the dashboard API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    bt = sub.add_parser("backtest", help="Run walk-forward backtest and print the report")
    bt.add_argument("--seed", type=int, default=7)
    bt.add_argument("--lag", type=int, default=None, help="execution lag in sessions (default 1)")
    bt.add_argument("--no-cost", action="store_true", help="zero transaction costs")

    ingest = sub.add_parser("ingest", help="Load PTR JSON + adj-close into the warehouse")
    ingest.add_argument("--trades", type=Path, required=True)
    ingest.add_argument("--prices", type=Path, required=True)
    ingest.add_argument("--db", type=Path, default=Path("data/congress_alpha.db"))
    ingest.add_argument("--source", default="ptr")
    ingest.add_argument("--politicians", type=Path, default=None)
    ingest.add_argument("--securities", type=Path, default=None)
    ingest.add_argument("--committees", type=Path, default=None)

    run = sub.add_parser("run", help="Walk-forward from an ingested warehouse")
    run.add_argument("--db", type=Path, default=Path("data/congress_alpha.db"))
    run.add_argument("--dash", type=Path, default=Path("data/dashboard.json"))
    run.add_argument("--brief", type=Path, default=Path("data/research_brief.md"))

    br = sub.add_parser("brief", help="Write the research memo from dashboard JSON")
    br.add_argument("--dash", type=Path, default=Path("data/dashboard.json"))
    br.add_argument("--out", type=Path, default=Path("data/research_brief.md"))

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        from congress_alpha.pipeline import run_demo

        payload = run_demo(db_path=args.db, seed=args.seed)
        _print_metrics(payload)
        print()
        print("wrote", args.db, "and data/dashboard.json")
        print("research brief: data/research_brief.md")
        print("next: python -m congress_alpha serve")
        return 0

    if args.cmd == "serve":
        import uvicorn

        from congress_alpha.pipeline import DEFAULT_DASH, run_demo

        if not DEFAULT_DASH.exists():
            print("no dashboard yet; running demo first...")
            run_demo()
        uvicorn.run("congress_alpha.api:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.cmd == "backtest":
        from datetime import date

        from congress_alpha.costs import CostModel
        from congress_alpha.generate import generate
        from congress_alpha.pipeline import _invoke_backtest
        from congress_alpha.prices import PriceStore
        from congress_alpha.report import format_report

        uni = generate(seed=args.seed)
        store = PriceStore(uni.prices)
        securities = {s.ticker: s for s in uni.securities}
        committees = {c.committee_id: c for c in uni.committees}
        lag = 1 if args.lag is None else args.lag
        costs = (
            CostModel(commission_bps=0.0, half_spread_bps=0.0, impact_k=0.0)
            if args.no_cost
            else CostModel()
        )
        result = _invoke_backtest(
            uni.trades,
            securities,
            uni.politicians,
            committees,
            store,
            start=date(2022, 6, 1),
            end=uni.end,
            execution_lag=lag,
            cost_model=costs,
            run_ablations=True,
        )
        print(format_report(result))
        _print_ablations(getattr(result, "ablations", None) or {})
        return 0

    if args.cmd == "ingest":
        from congress_alpha.ingest import apply_ingest

        report = apply_ingest(
            args.db,
            trades_path=args.trades,
            prices_path=args.prices,
            source=args.source,
            politicians_path=args.politicians,
            securities_path=args.securities,
            committees_path=args.committees,
            reset=True,
        )
        pub = report.as_public_dict()
        n_acc = pub.get("n_accepted", getattr(report, "n_accepted", None))
        n_rej = pub.get("n_rejected", getattr(report, "n_rejected", None))
        print(f"ingest n_accepted={n_acc} n_rejected={n_rej}")
        out = Path("data/ingest_report.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(pub, indent=2, default=str))
        print("wrote", out)
        return 0

    if args.cmd == "run":
        from congress_alpha.pipeline import run_from_db

        payload = run_from_db(db_path=args.db, dash_path=args.dash, brief_path=args.brief)
        _print_metrics(payload)
        print()
        print("wrote", args.dash, "and", args.brief)
        return 0

    if args.cmd == "brief":
        from congress_alpha.brief import write_brief

        payload = json.loads(args.dash.read_text())
        path = write_brief(payload, args.out)
        print("wrote", path)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
