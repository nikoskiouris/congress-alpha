# Congress Alpha V1 — model & engineering spec

Status: implemented in this repo. First version has **no ML**. Warehouse + event-time backtester + weighting engine. Once several years of clean point-in-time data exist, swap the hand weights for regression / gradient boosting / Bayesian shrinkage without changing the event clock.

## 1. Question

Not “what did Congress buy?”

> Which publicly disclosed congressional trades historically contain useful information after reporting delay, politician skill, industry expertise, trade size, consensus, and market conditions?

## 2. Legal clocks (the design constraint)

STOCK Act Periodic Transaction Reports (PTRs):

- House: file by the earlier of 30 days after notification or 45 days after the transaction. Source: House Committee on Ethics PTR instructions.
- Senate: file no later than 30 days after written notification, and in no case later than 45 days after the transaction. Source: Senate Select Committee on Ethics.
- Covered: purchase, sale, or exchange of covered securities over $1,000, including certain spouse / dependent-child transactions.
- Public systems: [House Clerk disclosures](https://disclosures-clerk.house.gov/), [Senate eFD](https://efdsearch.senate.gov/).

**Backtest law:** if NVDA is bought 2026-06-01 and disclosed 2026-07-10, the model’s as-of time for that event is 2026-07-10. Using 2026-06-01 is look-ahead and is a bug.

## 3. Event

Every disclosed transaction is:

```
politician, ticker, trade_date, disclosure_date, side, amount_range, owner, committees[]
```

`trade_date` is a **feature** (for lag `d = disclosure_date - trade_date` and the already-moved penalty). It is not a timestamp the strategy may act on.

Warehouse DDL: [`schema.sql`](schema.sql).

## 4. Formulas

### 4.1 Per-trade contribution

```
s_{p,i,t} = Direction
          × w_{p,sector(i),t}
          × DelayDecay(d)
          × Conviction(band)
          × Confidence(band)
          × Life(t − disclosure_date)
          × PremoveDecay(p, i, t)
```

Direction is `+1` buy / `−1` sell.

### 4.2 Politician skill (post-disclosure only)

Horizons `h ∈ {5, 20, 60, 120}` trading-day equivalents. For each completed trade:

```
α_{p,h,trade} = Direction × [ R(ticker, disclosure, disclosure+h) − R(SPY, same) ]
```

A trade may enter the training set for horizon `h` only if `disclosure_date + eval(h) < as_of`.

Recency: exponential half-life 2 years on `disclosure_date`.

Shrinkage:

```
ᾱ = (n · mean + n0 · 0) / (n + n0)     n0 = 12 overall, 8 sector
w_h = tanh(ᾱ / 0.06) · n / (n + 6)
w_p = Σ_h λ_h w_h                       λ = {5:0.15, 20:0.40, 60:0.30, 120:0.15}
```

Sector weights `w_{p,s}` are the same estimator on the sector subset, blended back to `w_p` when `n_s` is small. Committee membership is **not** an automatic information-advantage boost. It is stored as a feature and shown on the WHY panel. A mild interaction is not applied in V1 on purpose.

### 4.3 Delay decay

`d = disclosure_date − trade_date`, bucketed 0–7 / 8–14 / 15–30 / 31–45 / 45+.

```
remaining(bucket) = E[α_20 | bucket] / E[α_20 | 0–7]
```

shrunk toward `exp(−0.035 · bucket_start)`. The illustrative 100%/78%/41%/17%/4% table in the product note is **not** hard-coded. The engine learns the curve.

### 4.4 Conviction and confidence

Congressional filings report bands, not sizes. V1 uses the geometric midpoint:

```
mid = √(amount_min · amount_max)
conviction = clip( ln(mid) / ln(1e6), 0.20, 1.60 )
confidence = 1 / (1 + ln(amount_max / amount_min))
```

Do not treat $15,001–$50,000 as exactly $32,500.

### 4.5 Life and already-moved

```
Life = 1 for 0–20 days after disclosure, linear to 0 at 90 days
PremoveDecay = max(0, 1 − 0.85 · α_pre / (α_pre_typical + α_post_typical))
```

If the name already did the politician’s typical whole move between trade and filing, the live trade is ignored. That is the “bought at 100, disclosed at 145” case.

### 4.6 Consensus and portfolio

```
Signal_i = Σ_p s_{p,i,t}
weight_i = max(Signal_i, 0) / Σ_j max(Signal_j, 0)
```

subject to: stock ≤ 10%, sector ≤ 30%, ≥ 2 politicians, min signal, min dollar volume, 90-day expiry. Leftover weight is cash (0 excess vs a T-bill; vs SPY this is a drag in bull markets — honest).

Three books run on the same event clock:

1. **Congress Momentum** — all skill-weighted recent disclosed flow.
2. **Congress Conviction** — `w_p ≥ 0.25` only.
3. **Congress Consensus** — ≥ 3 independent predictive politicians, same side, 21-day window.

## 5. Training / walk-forward

```
for each Wednesday t after warmup:
    fit w_{p,s} and DelayDecay using trades with closed label windows < t
    build Signal_i from trades with disclosure_date ≤ t
    apply gates → portfolio P_t
    realize returns from t → next Wednesday on P_t
```

Warmup is first disclosure + 180 days so 120-day labels exist. No shuffling. No expanding window that includes the holding period. Nested: labels used at `t` are returns that finished before `t`.

**Forbidden:** measuring politician “skill” from `trade_date`, filling signals on `trade_date`, using same-day close on `disclosure_date` as if you had seen the filing at the open without a next-session rule. V1 prices the holding period from rebalance date closes (weekly), which is conservative.

## 6. Graph (V1 tables, V2 features)

```
Politician — Committee — Industry — Company — Trade — Legislation
```

V1 stores politician↔committee↔sector↔trade. Lobbying, campaign finance, geography, bill text: not in V1. A 2026 temporal-graph paper already showed walk-forward matters; this repo copies that discipline, not that graph.

## 7. Output

The product sentence is not “Pelosi bought this.” It is:

> CongressModel currently recommends a 7.4% position in LMT because five independently predictive congressional traders recently accumulated it, their historical defense-sector post-disclosure alpha is strong, and only 28% of the model’s estimated signal has decayed since the transactions.

UI: `frontend/index.html` (Congress score, bars, model book, WHY panel).

## 8. What V1 will not do

- Copy every trade equally.
- Rank politicians by name recognition.
- Assume committee membership = insider edge.
- Train on the evaluation week.
- Claim the synthetic demo is a live edge. Demo data is a planted DGP so tests can fail if the clock is wrong.

## 9. Next estimators (after clean PIT data)

Replace `tanh` weights with:

- pooled empirical Bayes by chamber / seniority / sector
- gradient boosting on `(α_h, hit_rate, n, recency, lag, committee_match, band, owner)`
- hierarchical Bayesian `w_{p,s}`

Same labels. Same walk-forward. Same prohibition on `trade_date` as event time.
