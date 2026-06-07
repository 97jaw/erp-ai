#!/usr/bin/env bash
# Verify Prometheus rules and Alertmanager config (Monitoring Phase 6)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROM="${OOA_PROMETHEUS_URL:-http://127.0.0.1:9090}"
AM="${OOA_ALERTMANAGER_URL:-http://127.0.0.1:9093}"

echo "== OOA Alerts verification (Phase 6) =="

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || true
  set +a
fi

echo ""
echo "Rendering Alertmanager config from .env..."
if ! python3 scripts/render_alertmanager_config.py; then
  echo "[FAIL] render_alertmanager_config.py"
  exit 1
fi

GEN="monitoring/alertmanager/alertmanager.generated.yml"
if [ ! -f "$GEN" ]; then
  echo "[FAIL] Missing $GEN"
  exit 1
fi
echo "[OK]   $GEN exists"

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'ooa-alertmanager'; then
  if docker exec ooa-alertmanager amtool check-config /etc/alertmanager/alertmanager.yml >/dev/null 2>&1; then
    echo "[OK]   Alertmanager config valid (amtool in container)"
  else
    echo "[WARN] Could not validate config inside container (restart after render):"
    echo "         docker compose -f docker-compose.monitoring.yml restart alertmanager"
  fi
fi

if curl -sf --max-time 5 "$AM/-/healthy" >/dev/null 2>&1; then
  echo "[OK]   Alertmanager healthy ($AM)"
else
  echo "[WARN] Alertmanager not reachable at $AM"
fi

rules_json="$(curl -sf --max-time 5 "$PROM/api/v1/rules" 2>/dev/null || true)"
if [ -z "$rules_json" ]; then
  echo "[WARN] Prometheus rules API not reachable"
else
  count="$(printf '%s' "$rules_json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
groups = d.get('data', {}).get('groups') or []
names = []
for g in groups:
    for r in g.get('rules') or []:
        if r.get('type') == 'alerting':
            names.append(r.get('name'))
print(len(names))
for n in sorted(set(names)):
    print(n)
" 2>/dev/null || echo "0")"
  total="$(echo "$count" | head -1)"
  echo "[OK]   Prometheus alerting rules loaded: $total"
  echo "$count" | tail -n +2 | sed 's/^/         /'
fi

if grep -q 'ALERT_EMAIL_ENABLED=true' .env 2>/dev/null || grep -q 'ALERT_SLACK_ENABLED=true' .env 2>/dev/null; then
  if grep -qE 'email_configs:|slack_configs:' "$GEN"; then
    echo "[OK]   Notification receivers present in generated config"
  else
    echo "[WARN] Alerts enabled in .env but no receivers in $GEN — check API keys/webhook"
  fi
else
  echo "[INFO] Email/Slack alerts disabled — firing alerts visible in Grafana/Prometheus/admin UI only"
  echo "       Enable ALERT_EMAIL_ENABLED or ALERT_SLACK_ENABLED in .env, then re-render"
fi

echo ""
echo "Runbooks: monitoring/MONITORING_RUNBOOKS.md"
echo "Access:   docs/MONITORING_ACCESS.md"
echo "Admin UI: http://localhost:8000/admin/monitoring → Alerts"
