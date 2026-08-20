# Roadmap (rollout)

Leadership wants features before rollout. Live congressional alpha is **not measured**. Do not pretend.

## Stage A — honest research demo (NOW)
Engine works on a planted DGP. Phone UI exists. GO lives here.

Ships: watermarks, ingest health on phone, API tests, extra ablations, WHY numbers.

## Stage B — real filings, still not a live book
Convenience watcher JSON → warehouse on `disclosure_date`. Prices adj-close. Reject options, bad clocks, unparsed bands.

Done when: `python -m congress_alpha ingest` on a real-shaped dump + `run` produces a brief watermarked RESEARCH FILE.

## Stage C — years of PIT (not this month)
Official House Clerk / Senate eFD as legal source. Frozen as-of snapshots. Then estimators may change.

## Stage D — blocked
AWS, ML, brokerage, "copy Pelosi". Do not pick these on `go`.

## Invent-ticket heuristic
When backlog empty, TPO files one ticket from this order:

1. Honesty / watermark / leakage audit missing in UI or API
2. Ingest reject-reasons or price holes
3. Clock-law tests
4. Phone demo that helps a director screenshot
5. Ablations that can falsify skill
6. Never D, never trade_date event clock
