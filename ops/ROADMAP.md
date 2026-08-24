# Roadmap (rollout)

Leadership wants a research app that can eventually inform real trades. Live brokerage is **not** in V1. Live congressional alpha is **not measured**. Do not pretend.

Director 2026-08-24: fake DGP forever is useless. `go` must walk toward frozen real filings. Do not scrape House Clerk / Senate eFD until the dump pipe works. Do not build S3 as the hot store.

## Stage A — honest research demo (closing)
Engine works on a planted DGP so clock tests can fail loud. Remaining A work only if it helps the dump on-ramp (ingest hygiene, price holes). Phone chrome on fake names waits.

## Stage B — real filings, still not a live book (NEXT)
Frozen public dump → warehouse on `disclosure_date` → phone RESEARCH FILE. Prices are a frozen adj-close snapshot, not a scrape on page load. Reject options, bad clocks, unparsed bands.

Done when: one command on a real-shaped dump + prices produces a brief watermarked RESEARCH FILE the phone can serve. Still not a broker. Still not a live track record.

## Stage C — official PIT (Director unblocks)
Official House Clerk / Senate eFD as legal source. Frozen as-of snapshots. Then estimators may change.

## Stage D — blocked
AWS-as-cosplay, ML, brokerage, "copy Pelosi". Do not pick these on `go`. S3 in `infra/aws.md` is a later attic for raw files, not today's loop.

## Invent-ticket heuristic
When backlog empty, TPO files one ticket from this order:

1. Dump → warehouse → phone RESEARCH FILE (missing piece of Stage B)
2. Frozen prices / ingest reject-reasons / price holes
3. Clock-law tests
4. Ablations that can falsify skill on ingested mode
5. Phone screenshot only if it shows ingested research, not extra fake-demo chrome
6. Never D, never trade_date event clock, never broker
7. Never invent CA-009/CA-010 on a normal `go` (Director unblocks)
