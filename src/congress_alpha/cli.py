from __future__ import annotations

import argparse
import sys
from pathlib import Path


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

    sub.add_parser("backtest", help="Print strategy comparison from the last demo")

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        from congress_alpha.pipeline import run_demo

        payload = run_demo(db_path=args.db, seed=args.seed)
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
        for row in payload["top_signals"][:6]:
            print(f"  {row['ticker']:6} {row['score']:3}  n={row['n_politicians']}")
        print()
        print("wrote", args.db, "and data/dashboard.json")
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
        import json

        from congress_alpha.pipeline import DEFAULT_DASH, run_demo

        if not DEFAULT_DASH.exists():
            run_demo()
        payload = json.loads(DEFAULT_DASH.read_text())
        print(f"{'strategy':12} {'cagr':>8} {'excess':>8} {'sharpe':>7} {'maxdd':>8}")
        for name, m in payload["metrics"].items():
            print(
                f"{name:12} {m['cagr']:8.1%} {m['excess_cagr']:8.1%} "
                f"{m['sharpe']:7.2f} {m['max_dd']:8.1%}"
            )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
