# CONGRESS ALPHA — RESEARCH BRIEF

## Classification

**SYNTHETIC DEMO**

THESE NUMBERS ARE NOT A LIVE TRACK RECORD. This memo is the output of a planted synthetic Congress (fictional names, planted skill). It is not live congressional alpha, not a composite, and not a number that can be allocated to.

Mode: `synthetic`
As of: 2026-06-24
Execution lag: 1 session(s)
Cost model: commission=1.0bps half_spread=4.0bps impact_k=5.0 aum=10000000 lag=1

## Product statement

The model answers one question:

> Which publicly disclosed congressional trades historically contain useful information after reporting delay, politician skill, industry expertise, trade size, consensus, and already-happened price moves?

That is post-disclosure information after delay, skill, size, consensus, and moves that have already happened. The engine never pretends it could have bought on the private trade date.

## Clock rules

disclosure_date is the only legal event time; trade_date never.

| Clock | Allowed |
|---|---|
| disclosure_date | yes |
| disclosure_date + horizon for labels (window closed) | yes |
| trade_date | never |

Senate/House PTRs can legally arrive 30/45 days late. A June 1 NVDA buy disclosed July 10 is tradable (or not) on July 10, not June 1.

## Headline walk-forward metrics

Next-session fill, costs on, DISCLOSURE clock only. Books: conviction, consensus, momentum, spy (if present).

| Book | CAGR | Excess | Sharpe | t-stat | Max DD | DSR |
|---|---:|---:|---:|---:|---:|---:|
| conviction | 7.0% | 4.9% | 0.21 | 0.41 | -0.9% | 0.00 |
| consensus | 2.1% | -0.0% | -0.08 | -0.16 | -0.5% | 0.00 |
| momentum | 7.5% | 5.3% | 0.25 | 0.47 | -1.2% | 0.00 |
| spy | 2.1% | 0.0% | 0.20 | 0.40 | -31.7% | 0.00 |

## Ablations

Same walk-forward, one knob removed at a time. Read against conviction.

| Ablation | Strategy | CAGR | Excess | Sharpe | t-stat | Max DD |
|---|---|---:|---:|---:|---:|---:|
| equal_skill | conviction | 6.5% | 4.3% | 0.19 | 0.36 | -1.6% |
| no_delay_decay | conviction | 7.1% | 4.9% | 0.22 | 0.42 | -1.3% |
| placebo_skill | conviction | 1.6% | -0.5% | -0.11 | -0.22 | -2.0% |

Interpretation:
- If equal_skill Sharpe is close to conviction, skill ranking may not be doing work.
- placebo_skill should be weaker than conviction if planted or real skill exists.
- Observed: equal_skill Sharpe 0.19 vs conviction 0.21 (gap 0.03). Skill ranking may not be doing work.
- Observed: placebo_skill Sharpe -0.11 is weaker than conviction 0.21, consistent with planted or real skill.
- equal_skill: All politicians get identical weight. Tests whether skill ranking matters.
- no_delay_decay: Delay decay disabled (all lag buckets=1). Tests whether reporting lag is priced.
- placebo_skill: Permute w_p across politicians each week. Should destroy planted skill.

## Leakage audit

These counts exist so a reader can see the DISCLOSURE clock working.

- trades: 199
- delayed filings (trade_date before disclosure_date): 199
- trade_date traps still private at last as_of: 0
- disclosures after last as_of: 0
- note: trade_date traps are filings the public has not seen yet. Using them as event time is look-ahead. This engine never does.

## Event study (20d, post-disclosure vs SPY)

CARs start the next session after disclosure_date. Skill buckets use the last weight known strictly before that date.

- all 20d: mean 4.2%  t=6.00  n=188  hit=66.5%
- skilled 20d: mean 9.7%  t=8.18  n=62  hit=85.5%

## What this does NOT claim

- Not investment advice and not a recommendation to buy or sell anything.
- Not a Pelosi-copy product and not a celebrity-trader feed.
- Not live AUM, not a live track record, and not a number that can be allocated to.
- Demo numbers are a planted data-generating process unless this file is ingested research.

## What's next

- Drop official PTR JSON and adj-close CSV into ingest (`python -m congress_alpha ingest`, then `python -m congress_alpha run`).
- No ML until clean point-in-time years exist.
- No AWS required for research.

## Disclaimer

Synthetic demonstration. Not investment advice. Signals are computed from disclosure_date, never trade_date. Backtest fills next session after the signal date and pays spread/impact costs. Numbers are not a live track record.
