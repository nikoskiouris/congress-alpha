# Congress Alpha

Event-time **Congressional Trading Factor Model**. Not a Pelosi-copy feed.

The model answers one question:

> Which publicly disclosed congressional trades historically contain useful information *after* reporting delay, politician skill, industry expertise, trade size, consensus, and already-happened price moves?

It never pretends it could have bought on `trade_date`. Senate/House PTRs can legally arrive 30/45 days late. If NVDA was bought June 1 and disclosed July 10, the backtest buys (or doesn’t) on July 10.

## Status (leadership)

- V1 engine: done (event-time, costs, next-session, PIT event study)
- Live congressional alpha: NOT measured (demo is a planted DGP)
- This sprint: ingest path, ablations, research brief, CI
- Company demo: `python -m congress_alpha demo` then `serve`; read `data/research_brief.md`

```
Signal_stock,t  =  Σ_p  w_p,s,t  ·  s_p,stock,t
```

`w` is learned from **post-disclosure** excess returns vs SPY. `s` is one disclosed trade’s contribution after delay decay, conviction, confidence, signal life, and pre-move decay.

## Phone / first run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m congress_alpha demo
python -m congress_alpha serve
```

Open `http://127.0.0.1:8000`. Dashboard is mobile-first.

`demo` builds a **synthetic** Congress (fictional names, planted ground-truth skill), walk-forward backtests three books, writes `data/congress_alpha.db` + `data/dashboard.json`.

```bash
python -m congress_alpha backtest
```

Walk-forward is next-session, costed, with Newey-West t-stats, a cost sweep, and a point-in-time event study. It never uses `trade_date` as an event time.

| Book | Rule |
|---|---|
| **conviction** | only politicians with historically strong post-disclosure weights |
| **consensus** | ≥3 independent predictive filers, same side, 21-day window |
| **momentum** | all recent disclosed flow, skill-weighted |

## Time realism (non-negotiable)

| Clock | Allowed? |
|---|---|
| `disclosure_date` | yes — this is when the public sees the trade |
| `disclosure_date + horizon` for training labels | yes — only after the window has **closed** |
| `trade_date` as an event time | **never** |

Tradable alpha for a politician is:

```
α_tradable = return(disclosure → t+h) − SPY
```

not the prettier number measured from the private trade date.

## Formula (V1, no ML)

```
contribution = Direction
             × Politician×SectorSkill
             × DelayDecay(lag)
             × Conviction(geom_mid of amount band)
             × Confidence(band width)
             × Life(days since disclosure)
             × PremoveDecay(already-moved)

Signal_i = Σ contribution
weight_i = max(Signal_i, 0) / Σ max(Signal_j, 0)
```

Gates: max stock 10%, max sector 30%, min 2 politicians, min signal, 90-day expiration, leftover is cash.

Conviction uses a **log geometric midpoint** of the STOCK Act band. A $15,001–$50,000 line is not $32,500 pretending to be exact.

## Repo map

```
spec/schema.sql          point-in-time warehouse
spec/MODEL.md            formulas, training, backtest, ingest rules
infra/aws.md             V1 AWS/Python architecture
src/congress_alpha/      engine, ingest, ablations, API, synthetic DGP
data/fixtures/           fictional watcher JSON + prices for ingest tests
frontend/index.html      Congress Signal UI
tests/                   look-ahead, skill recovery, ingest, ablations
```

## Real filings later

House Clerk public financial disclosures and Senate eFD/PTR systems are the legal source. `python -m congress_alpha fetch --source house-watcher --out data/raw/` (or `senate-watcher`) writes a **convenience dump** plus `manifest.json` (`fetched_at`, source URL, sha256); it does not rename `disclosure_date`. `congress_alpha.ingest` can read that JSON still keyed on `disclosure_date`. Do not train on `transaction_date`.

```bash
python -m congress_alpha ingest \
  --trades data/fixtures/trades_ok.json \
  --prices data/fixtures/prices.csv \
  --politicians data/fixtures/politicians.json \
  --securities data/fixtures/securities.json \
  --committees data/fixtures/committees.json \
  --db data/congress_alpha.db

python -m congress_alpha run --db data/congress_alpha.db
python -m congress_alpha brief --dash data/dashboard.json --out data/research_brief.md
```

`ingest` writes `data/ingest_report.json`. `run` is the ingested walk-forward (`mode=ingested`); `demo` stays synthetic. Neither is a live track record.

This is research software, not advice. Demo data is fictional on purpose.

See [spec/MODEL.md](spec/MODEL.md) for schema, training, walk-forward rules, and the three-strategy protocol.

## Director loop (phone)

New Cursor chat. Type **`go`**. That is the whole instruction.

The agent is technical product owner. It picks the next ticket from `ops/`, briefs engineer subagents, tests, and **auto-merges to main**. It does not wait for you. Constitution: `AGENTS.md`. Board: `python3 ops/next.py`.

Other one-liners: `status` · `idea …` · `fix` · `stop`.
