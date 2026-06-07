# Phase 10 load testing (k6)

## Prerequisites

- Gateway running locally: `uvicorn gateway.main:app --port 8000`
- k6 installed: `brew install k6` (macOS) or [k6.io/docs](https://k6.io/docs/get-started/installation/)
- `.env` with `OOA_DB_URL`, Odoo credentials, `JWT_SECRET`
- Dev super-admin file ID in `.env` (`SUPER_ADMIN_FILE_ID=2721`)

## Pre-auth JWT (optional)

```bash
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"file_id":"2721"}' | jq -r .access_token
```

Export for k6:

```bash
export OOA_JWT="<token>"
```

## Run load test

From repo root (`odoo_ai_bridge/`):

```bash
k6 run scripts/load/phase10_chat_stream.js
```

Environment overrides:

```bash
OOA_API_BASE=http://127.0.0.1:8000 SUPER_ADMIN_FILE_ID=2721 k6 run scripts/load/phase10_chat_stream.js
```

## Pass criteria

| Metric | Target |
|--------|--------|
| p50 `ooa_chat_stream_duration_ms` | < 3000 ms |
| p95 | < 8000 ms |
| Stream errors | < 1% of iterations |
| VUs | 10 concurrent, 5 minutes |

Summary JSON: `reports/phase10_k6_summary.json`

## Baseline + DB telemetry

After k6 (or standalone):

```bash
python scripts/phase10_baseline.py
python scripts/phase10_acceptance.py
```
