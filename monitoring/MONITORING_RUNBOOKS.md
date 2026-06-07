# OOA Monitoring Runbooks

Use with **Admin → Monitoring → Alerts** or Prometheus/Alertmanager UIs.

## OoaGatewayDown (critical)

1. `curl -sf http://127.0.0.1:8000/health` — if fail, restart gateway: `bash scripts/start_gateway.sh`
2. Ensure `OOA_GATEWAY_HOST=0.0.0.0` so Docker Prometheus can scrape port 8000
3. `./scripts/check_gateway_scrape.sh` and `./scripts/set_prometheus_gateway_target.sh`
4. Check `logs/ooa-gateway.jsonl` or Grafana → Loki → `{job="ooa-gateway"}`

## OoaAPIProviderDown (critical)

1. Admin → Monitoring → API Health → **Refresh**
2. Verify API keys in `.env` for the failing `provider` label
3. Check vendor status pages (Anthropic, OpenAI, ElevenLabs)
4. Silence via admin if planned maintenance: POST `/admin/alerts/silence`

## OoaAnthropicCreditsLow / OpenAI / ElevenLabs

1. Top up vendor billing
2. Set `ANTHROPIC_CREDIT_BUDGET_CENTS` for Anthropic balance alerts
3. Admin → Usage for spend breakdown

## OoaHighErrorRate (high)

1. Grafana or Admin logs — filter `ERROR`
2. Correlate with Odoo outages or recent deploys
3. Inspect `ooa_api_requests_total` by `status_code` in Prometheus

## OoaPostgresExporterDown (high)

1. Confirm `OOA_DB_URL` / `POSTGRES_EXPORTER_DSN` match a running Postgres
2. Homebrew: port 5432; Docker admin DB: `docker compose -f docker-compose.admin-db.yml up -d` on 5433
3. `docker compose -f docker-compose.monitoring.yml restart postgres_exporter`

## OoaHighLoginFailureRate (medium)

1. Admin audit / security logs
2. Review `AUTH_LOGIN_LIMIT`, `AUTH_LOCKOUT_MINUTES` in `.env`
3. Consider IP blocking at reverse proxy

## Test alert pipeline

```bash
./scripts/verify_alerts.sh
# Optional: fire test alert (shows in Prometheus, may not notify if email/Slack disabled)
curl -X POST http://127.0.0.1:9093/api/v2/alerts -H 'Content-Type: application/json' -d '[]'
```

Prometheus rules: `monitoring/prometheus/rules/ooa-alerts.yml`  
Alertmanager config: `monitoring/alertmanager/alertmanager.generated.yml` (from `scripts/render_alertmanager_config.py`)
