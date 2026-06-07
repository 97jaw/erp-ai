#!/usr/bin/env bash
# Verify OOA monitoring stack (Phases 2–3: metrics + logs)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROM="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GW="${OOA_GATEWAY_URL:-http://127.0.0.1:8000}"
GRAFANA="${GRAFANA_URL:-http://127.0.0.1:3030}"
ALERTMGR="${ALERTMANAGER_URL:-http://127.0.0.1:9093}"
LOKI="${LOKI_URL:-http://127.0.0.1:3100}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env 2>/dev/null || true
  set +a
fi

if [ -f scripts/render_alertmanager_config.py ]; then
  python3 scripts/render_alertmanager_config.py >/dev/null 2>&1 || true
fi

echo "== OOA Monitoring verification =="
echo "Prometheus: $PROM"
echo "Gateway:    $GW"
echo ""

fail=0
gw_fail=0
mon_fail=0

check() {
  local name="$1"
  local url="$2"
  local kind="${3:-mon}"
  if curl -sf --connect-timeout 3 --max-time 5 "$url" >/dev/null 2>&1; then
    echo "[OK]   $name"
    return 0
  fi
  echo "[FAIL] $name ($url)"
  fail=1
  if [ "$kind" = "gw" ]; then gw_fail=1; else mon_fail=1; fi
  return 1
}

# --- Preflight: Docker (monitoring containers) ---
if ! command -v docker >/dev/null 2>&1; then
  echo "[WARN] docker not in PATH — install Docker Desktop for Prometheus/Grafana."
elif ! docker info >/dev/null 2>&1; then
  echo "[WARN] Docker engine not reachable (compose may have run, then engine stopped)."
  echo "       open -a Docker  &&  docker desktop status  # wait for: running"
  echo "       ./scripts/diagnose_monitoring.sh"
  echo ""
else
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'ooa-prometheus'; then
    echo "[OK]   Docker monitoring stack has running containers"
  else
    echo "[WARN] Monitoring containers may not be up. Run:"
    echo "         docker compose -f docker-compose.monitoring.yml up -d"
    echo ""
  fi
fi

echo ""
check "Prometheus UI" "$PROM/-/healthy"
check "Grafana UI" "$GRAFANA/api/health"
check "Alertmanager" "$ALERTMGR/-/healthy"
check "Loki" "$LOKI/ready"
check "Gateway /health" "$GW/health" gw
check "Gateway /metrics" "$GW/metrics" gw

echo ""
echo "Prometheus targets:"
targets_json="$(curl -sf --max-time 5 "$PROM/api/v1/targets" 2>/dev/null || true)"
if [ -z "$targets_json" ]; then
  echo "  (skipped — Prometheus not reachable at $PROM)"
else
  printf '%s' "$targets_json" | python3 -c "
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    print('  (empty response from Prometheus)')
    sys.exit(0)
try:
    data = json.loads(raw)['data']['activeTargets']
except (json.JSONDecodeError, KeyError) as e:
    print(f'  (could not parse targets: {e})')
    sys.exit(0)
for t in sorted(data, key=lambda x: x['labels'].get('job','')):
    job = t['labels'].get('job', '?')
    health = t['health']
    last = t.get('lastError') or ''
    mark = 'UP' if health == 'up' else 'DOWN'
    print(f'  {mark:4} {job:20} {last[:80]}')
" || echo "  (error printing targets)"
fi

echo ""
if curl -sf --max-time 3 "$GW/health" >/dev/null 2>&1; then
  if ! curl -sf --max-time 3 "$PROM/api/v1/targets" 2>/dev/null | grep -q '"job":"ooa-gateway".*"health":"up"'; then
    echo "[HINT] ooa-gateway target DOWN but host gateway OK — Docker cannot reach port 8000:"
    echo "       OOA_GATEWAY_HOST=0.0.0.0 bash scripts/start_gateway.sh"
    echo "       ./scripts/check_gateway_scrape.sh && ./scripts/set_prometheus_gateway_target.sh"
  fi
fi

echo ""
if curl -sf --max-time 5 "$GW/metrics" 2>/dev/null | grep -q ooa_api_requests_total; then
  echo "[OK]   OOA custom metrics present on gateway"
  if curl -sf --max-time 5 "$GW/metrics" 2>/dev/null | grep -q ooa_api_provider_up; then
    echo "[OK]   API provider health metrics (Phase 4)"
  else
    echo "[WARN] ooa_api_provider_up not found — restart gateway after Phase 4 deploy"
  fi
else
  echo "[WARN] ooa_* metrics not found — start gateway with Phase 1 instrumentation:"
  echo "         bash scripts/start_gateway.sh"
fi

echo ""
LOG_FILE="${OOA_LOG_FILE:-logs/ooa-gateway.jsonl}"
if [ -f "$LOG_FILE" ]; then
  if tail -1 "$LOG_FILE" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "[OK]   Gateway JSON log file ($LOG_FILE)"
  else
    echo "[WARN] Log file exists but last line is not valid JSON: $LOG_FILE"
  fi
else
  echo "[WARN] No gateway log file yet — restart gateway after Phase 3 (writes $LOG_FILE)"
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx 'ooa-promtail'; then
  echo "[OK]   Promtail container running"
else
  echo "[WARN] Promtail not running (docker compose -f docker-compose.monitoring.yml up -d)"
fi

if curl -sf --max-time 5 "$LOKI/loki/api/v1/labels" >/dev/null 2>&1; then
  echo "[OK]   Loki accepting queries (Explore → Loki in Grafana)"
else
  echo "[WARN] Loki labels API not reachable"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "All core endpoints reachable."
  echo "Logs: Grafana → Explore → Loki → query {job=\"ooa-gateway\"}"
  echo "Alerts: ./scripts/verify_alerts.sh  |  docs/MONITORING_ACCESS.md"
  exit 0
fi

echo "Some checks failed."
if [ "$gw_fail" -eq 0 ] && [ "$mon_fail" -eq 1 ]; then
  echo "  Gateway is OK — only Docker monitoring needs to be started on this machine."
fi
if [ "$mon_fail" -eq 1 ]; then
  echo "  Monitoring:"
  echo "    ./scripts/diagnose_monitoring.sh"
  echo "    open -a Docker    # wait until: docker desktop status  →  running"
  echo "    docker compose -f docker-compose.admin-db.yml up -d"
  echo "    docker compose -f docker-compose.monitoring.yml up -d --force-recreate"
fi
if [ "$gw_fail" -eq 1 ]; then
  echo "  Gateway (keep running in another terminal):"
  echo "    bash scripts/start_gateway.sh"
fi
echo "  Then: ./scripts/verify_monitoring_stack.sh"
exit 1
