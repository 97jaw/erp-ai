# OOA Monitoring — Team Access

## URLs (local dev)

| Service | URL | Credentials |
|---------|-----|-------------|
| OOA Gateway + Admin UI | http://localhost:8000 | Admin login |
| Grafana | http://localhost:3030 | `admin` / `GRAFANA_ADMIN_PASSWORD` (default `admin`) |
| Prometheus | http://localhost:9090 | none |
| Alertmanager | http://localhost:9093 | none |
| Loki | http://localhost:3100 | via Grafana Explore |

## Start stack

```bash
# 1. Load env and render Alertmanager config (Phase 6)
python scripts/render_alertmanager_config.py

# 2. Gateway (separate terminal)
bash scripts/start_gateway.sh

# 3. Monitoring containers
docker compose -f docker-compose.monitoring.yml up -d

# 4. Verify
./scripts/verify_monitoring_stack.sh
./scripts/verify_alerts.sh
```

## Enable email or Slack alerts

Edit `.env`:

```bash
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com:587
ALERT_EMAIL_FROM=ooa-alerts@yourdomain.com
ALERT_EMAIL_TO=oncall@yourdomain.com
ALERT_EMAIL_USERNAME=...
ALERT_EMAIL_PASSWORD=...

# or
ALERT_SLACK_ENABLED=true
ALERT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Then re-render and restart Alertmanager:

```bash
python scripts/render_alertmanager_config.py
docker compose -f docker-compose.monitoring.yml restart alertmanager
```

## Admin monitoring UI

**Admin → Monitoring** (`/admin/monitoring`): Overview, AI operations, API health, **Odoo**, Infrastructure, **Users**, **Costs**, Logs, Alerts.

Requires permission `admin.settings.manage`.

## Grafana dashboards (folder: OOA)

| Dashboard | UID |
|-----------|-----|
| OOA Overview | `ooa-overview` |
| AI Operations | `ooa-ai-operations` |
| API Health | `ooa-api-health` |
| Odoo Integration | `ooa-odoo` |
| Infrastructure | `ooa-infrastructure` |
| User Activity | `ooa-user-activity` |
| Logs Explorer | `ooa-logs` |
| Alerts | `ooa-alerts` |

After adding dashboards, restart Grafana: `docker compose -f docker-compose.monitoring.yml restart grafana`

## Runbooks

See [monitoring/MONITORING_RUNBOOKS.md](../monitoring/MONITORING_RUNBOOKS.md).
