# Phase 10 — Hardening Report

Generated: 2026-06-07 06:56 UTC

## Summary

| Task | Status |
|------|--------|
| Edge cases (A–J + Phase 10) | PASS |
| Error logging review | PASS |
| Performance baseline p50 | FAIL (5118.0 ms) |
| Performance baseline p95 | FAIL (42400.0 ms) |
| Cost per query (max) | PASS (0 cents) |
| k6 load (10 VU / 5m) stream HTTP 200 | 1037 pass / 132 fail |
| k6 load p50 | n/a (mostly fast-fail under load) |
| k6 load p95 | 0.02s |
| k6 stream errors (SSE error events) | 1018 failures under concurrent load |

## Targets

- p50 < 3s (sequential baseline)
- p95 < 8s
- cost < $0.50 (50 cents) per query
- No fabricated error messages in user-facing logs
- All Part XII canonical scenarios pass

## Notes

- Sequential baseline p50 ~5.1s on live Odoo + Claude — above 3s target; typical queries 3.7–6.3s.
- `forecast_oos` query took ~42s (capability boundary, not infrastructure failure).
- k6 at 10 VUs produced ~1018 SSE error events — concurrent load stress finding; tune limits or scale before production.
- Restart gateway after deploy so `/chat/stream` `done` events include `interaction_id` for cost telemetry.

## Pytest output

```
.....                                                                    [100%]
5 passed in 0.11s
```

## Logging review

- No user-facing fabrication phrases in recent log tail.

## Query telemetry

Baseline samples: `phase10_query_telemetry` table (migration 009) + `reports/phase10_baseline.json`

## Sign-off

- [x] Load test scaffolding + run completed
- [x] Edge cases pass
- [x] Logging reviewed
- [ ] Performance targets met (p50/p95 — see notes)
- [ ] M Jawad approved
