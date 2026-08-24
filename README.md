# Congress Alpha

Event-time **Congressional Trading Factor Model**. Not a Pelosi-copy feed.

The model answers one question:

> Which publicly disclosed congressional trades historically contain useful information *after* reporting delay, politician skill, industry expertise, trade size, consensus, and already-happened price moves?

It never pretends it could have bought on `trade_date`. Senate/House PTRs can legally arrive 30/45 days late. If NVDA was bought June 1 and disclosed July 10, the backtest buys (or doesn’t) on July 10.

## Status (leadership)

- V1 engine: done (event-time, costs, next-session, PIT event study)
- Live congressional alpha: NOT measured (demo is a planted DGP)
- This sprint: **frozen real-dump on-ramp** (ingest hygiene → fixture on phone → frozen prices). Official House/Senate scrape still gated. Not a broker.
- Company demo: `python -m congress_alpha demo` then `serve`; read `data/research_brief.md`
- Future map: [What's next](#whats-next-future-map)

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

## What's next (future map)

TPO brainstorm, 2026-08. Ideas, not commitments — `go` still ships one ticket at a time and the board (`ops/`) decides. **Director 2026-08-24: walk `go` toward frozen real filings (Stage B dump + prices) before more fake-demo chrome or official scrape.** Two laws hold for every idea below: `disclosure_date` is the only event time, and nothing synthetic or ingested is ever presented as a live track record. Every idea ships with the test that could kill it.

### 1. Prove it or kill it — harsher judges (Stage B)

The demo already falsifies planted skill. Real filings deserve a harder court:

- **Factor court** — regress book excess on market / size / value / momentum. If "congress alpha" is repackaged beta or momentum, the brief says so automatically.
- **Naive-copy benchmark** — an equal-weight follow-everything book and a celebrity-only placebo as *benchmarks to beat*, never product surfaces. If the model cannot beat naive copying after costs, that is the finding.
- **Crowding decay curve** — post-disclosure CAR by calendar year. Copy-trading apps exploded after 2020; measure whether the disclosure pop is being arbitraged away instead of assuming.
- **Capacity curve** — sweep AUM through the impact model until excess hits zero. Publish "worth $X, not infinity".
- **Multiple-testing discipline** — books × horizons × ablations is a test zoo. Add SPA / reality-check p-values next to deflated Sharpe.

### 2. Receipts — an honest forward record without a brokerage (Stage B→C)

The watermark says "not a live track record". The only honest cure is time:

- **Signed shadow book** — every rebalance commits the book (hash + timestamp) before returns exist. After a year: an unfakeable out-of-sample paper record, still watermarked, but pre-registered.
- **Holdout vault** — when years of PIT filings land, lock the most recent years (hashed, untouched) until estimators are frozen. One evaluation per model version, ever.
- **Replay CI** — nightly job re-runs last week's fit from frozen snapshots and demands bit-identical output. Reproducibility as a test, not a promise.

### 3. PIT data engine — the real moat (Stage C)

Real filings are messy in ways the planted DGP is not:

- **Filing ledger** — append-only store with our own `first_seen_at` per filing version. Amendments supersede; the as-of view answers "what did the public know at time t", never "what is true today".
- **Identifier history** — tickers get reused and renamed. Map trades through time-stamped FIGI/CUSIP, not string equality, or labels get poisoned.
- **Survivorship-free prices** — delistings, halts, corporate actions in the price layer. A return that ends in delisting is a return, not a hole.
- **DGP zoo** — more synthetic worlds: no-skill Congress, late-filer Congress, amendment-storm Congress, clustered-disclosure Congress. Every honesty feature gets a world where cheating would be visible.

### 4. Richer events, same clock (Stage C+)

- **Senior-staff PTRs** — covered senior congressional staff file too. Less celebrity, less copy-app crowding, possibly more residual signal.
- **Sell asymmetry** — sells are often liquidity or diversification, not information. Split the estimator by side and let the data say.
- **Options as direction only** — rejected at ingest today. Either model as direction/sentiment with no size, or keep rejecting; decide with a test, not taste.
- **Graph features (V2)** — committees → bills → sectors as *features* under the same walk-forward discipline. Lobbying and donor edges later. No feature escapes the event clock.

### 5. Uncertainty and provenance as the product (Stage A/B, phone-first)

- **Ranges, not points** — WHY panel shows bootstrap/conformal intervals. A 7.4% position with a wide interval should look different on the phone.
- **Filing-level provenance** — tap a position, see the exact disclosures behind it: who, disclosed when, how stale, how much already moved.
- **Weekly diff brief** — "what changed since last Wednesday": new filings, decayed signals, turnover. The memo leadership actually reads.
- **Model card** — one page: what it does, what it cannot know, where it fails. Ships with every brief.

### 6. Platform play — a disclosure-clock engine (post-C)

Congress is instance #1 of a general machine: *mandatory disclosure with a legal lag, event-time backtest, falsification harness.*

| Instance | Lag law | Notes |
|---|---|---|
| Congress PTR | ≤ 30/45 days | this repo |
| Corporate insiders (Form 4) | 2 business days | exact sizes, no bands |
| 13F clones | 45 days after quarter end | crowded; good stress test |
| Activists (13D) | 5 business days | event-driven |

Same warehouse shape, same clock law, same ablations. The moat is the discipline, not the Congress gimmick.

### 7. Plan B with the same warehouse — transparency analytics (any stage)

If disclosure alpha is dead after costs, the data still pays rent:

- late-filing league tables (who blows the 45-day law, how often)
- amendment-pattern analysis (silent corrections after price moves)
- STOCK Act compliance scoring by member, chamber, committee

Journalists, academics, and compliance teams want this at exactly zero alpha. Same warehouse, same PIT rigor, zero pretense.

### 8. Harden the agent shop (Stage A, now)

The GO pipeline is a product too:

- **Red-team GO** — an `audit` command where an adversarial agent tries to sneak `trade_date` leakage or drop a watermark, and the suite must catch it. Mutation testing for the clock laws.
- **Scheduled GO** — nightly automation runs the board while the Director sleeps; morning report is four sentences.
- **Brief archive** — every research brief versioned with diffs, so "the numbers changed" is always answerable with "here is why".

### Pre-mortem — what kills this, and the counter

| Killer | Counter |
|---|---|
| Disclosure alpha gone after costs | crowding curve + factor court say it loudly; pivot to §7 |
| Ticker mapping poisons labels | identifier history (§3) before estimators change |
| Copy-apps front-run the pop | measure per year; capacity curve prices it |
| Backfilled "PIT" data lies about as-of | filing ledger with our own `first_seen_at` (§3) |
| One great backtest was luck | holdout vault + signed shadow book (§2) |

### Still forbidden, forever

Copy-Pelosi product. Advice. Hiding the synthetic banner. `trade_date` as event time. A working `cheat_backtest_on_trade_date`.

## Director loop (phone)

New Cursor chat. Type **`go`**. That is the whole instruction.

The agent is technical product owner. It picks the next ticket from `ops/`, briefs engineer subagents, tests, and **auto-merges to main**. It does not wait for you. Constitution: `AGENTS.md`. Board: `python3 ops/next.py`.

Other one-liners: `status` · `idea …` · `fix` · `stop`.
