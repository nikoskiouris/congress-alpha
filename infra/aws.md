# AWS / Python architecture (V1)

Local V1 in this repo is SQLite + FastAPI + a static phone UI. That is the research loop. Cloud is the same boxes with harder storage.

```
                    ┌─────────────┐
   House Clerk      │  raw zone   │      Senate eFD
   PTR / FD   ───►  │  S3 JSON    │ ◄──  PTR XML/HTML
                    │  + PDFs     │
                    └──────┬──────┘
                           │ parse (Lambda)
                           ▼
                    ┌─────────────┐
                    │  warehouse  │  RDS Postgres
                    │  PIT tables │  (see spec/schema.sql)
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        prices job    nightly fit   research box
        (Polygon /    w_p,s + delay  (ECS / SageMaker
         Tiingo)      decay curve     optional)
                           │
                           ▼
                    signals + books
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
        API (ECS/Fargate)         dashboard (S3+CF)
        FastAPI identical         same frontend/
```

## Jobs

| Job | Cadence | Rule |
|---|---|---|
| Ingest PTR | hourly during session | store filing time; never overwrite `disclosure_date` with `trade_date` |
| Prices | nightly | split-adjusted, next-session join |
| Fit | nightly after prices | walk-forward as-of = last complete session |
| Backtest | on model change | full PIT replay, three books |
| Serve | always | read snapshots, do not refit on request |

## Python map

- `congress_alpha.ingest` — normalize House/Senate (or watcher JSON) into `TradeEvent`
- `congress_alpha.skill` — `w_p`, `w_{p,s}`, delay curve
- `congress_alpha.signal` — three books
- `congress_alpha.backtest` — weekly event-time loop
- `congress_alpha.api` — dashboard JSON

Swap SQLite for Postgres by changing `warehouse.connect`. Schema is vanilla SQL.

## AWS sketch (when you leave the laptop)

- **S3** `s3://congress-alpha-{env}/raw/{source}/{yyyy}/{mm}/{dd}/`
- **RDS Postgres** (Multi-AZ later; single-AZ is fine for research)
- **EventBridge** schedule → **Lambda** ingest / **ECS Fargate** fit (fit is numpy, minutes not hours in V1)
- **ECR** image from this repo
- **ALB + ECS** for FastAPI
- **CloudFront + S3** for `frontend/`
- **Secrets Manager** for market-data keys
- **IAM** least privilege; no public RDS

No SageMaker in V1. The first model is the formulas in `spec/MODEL.md`. When you have years of PIT trades, drop a boosting job on the same label table.

## Local ≈ cloud

`python -m congress_alpha demo` is the entire pipeline with a planted DGP. Production replaces `generate.py` with ingest + vendor prices. The backtester does not change.
