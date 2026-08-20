# Congress Alpha

Event-time **Congressional Trading Factor Model**. Not a Pelosi-copy feed.

The model answers one question:

> Which publicly disclosed congressional trades historically contain useful information *after* reporting delay, politician skill, industry expertise, trade size, consensus, and already-happened price moves?

It never pretends it could have bought on `trade_date`. Senate/House PTRs can legally arrive 30/45 days late. If NVDA was bought June 1 and disclosed July 10, the backtest buys (or doesn’t) on July 10.

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
spec/MODEL.md            formulas, training, backtest rules
infra/aws.md             V1 AWS/Python architecture
src/congress_alpha/      engine, API, synthetic DGP
frontend/index.html      Congress Signal UI
tests/                   look-ahead + skill recovery
```

## Real filings later

House Clerk public financial disclosures and Senate eFD/PTR systems are the legal source. `congress_alpha.ingest` can read community House/Senate stock-watcher JSON **as a convenience**, still keyed on `disclosure_date`. Do not train on `transaction_date`.

This is research software, not advice. Demo data is fictional on purpose.

See [spec/MODEL.md](spec/MODEL.md) for schema, training, walk-forward rules, and the three-strategy protocol.
