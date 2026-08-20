---
id: CA-009
title: Official House Clerk / Senate eFD parse
priority: P3
status: blocked
type: research
effort: L
merge: auto
director_gate: true
blocked_by: ["CA-002"]
---

# CA-009 Official Clerk / eFD parse

## Why director
Legal source. Not this sprint. Convenience dumps first.

## Why engine
House Clerk + Senate eFD are the record. HTML/PDF/XML. Easy to grab transaction_date as as-of.

## Done when
- [ ] Parser keyed on filing/disclosure timestamp
- [ ] Same reject rules as ingest
- [ ] Fixture from a redacted public sample

## Forbidden
- GO picking this while Stage A/B tickets remain
- AWS as a side quest

## Engineer prompt
Do not start until CA-002 is done and Director unblocks. Official parse only. disclosure_date remains event time.
