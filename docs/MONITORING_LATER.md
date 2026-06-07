# Monitoring — Deferred (Phase 6+)

Phase 5 (admin dashboards + Grafana) is complete. Track these separately:

## Notifications
- [ ] Enable `ALERT_EMAIL_ENABLED` / `ALERT_SLACK_ENABLED` in production `.env`
- [ ] End-to-end test: fire alert → Slack/email received

## Admin API extras (MONITORING_PLAN Part X)
- [ ] `GET /admin/logs/export` — CSV export
- [ ] `GET /admin/logs/:id` — single log entry
- [ ] `GET /admin/traces?request_id=` — distributed trace view
- [ ] `POST /admin/alerts/:id/acknowledge`
- [ ] `GET /admin/alerts/history`
- [ ] `GET /admin/health` — composite health (gateway, DB, Prometheus, Odoo)

## Alert rules
- [ ] `OoaOdooSlowResponse` — Odoo p95 > 2s
- [ ] `OoaDatabaseConnectionsHigh` — Postgres pool / connections

## Instrumentation
- [ ] Update `ooa_active_users` gauge from admin usage job
- [ ] OpenTelemetry spans (optional)

## Ops
- [ ] Deploy monitoring stack on staging/production server
- [ ] Update `MONITORING_PLAN.md` checkboxes to reflect completion
