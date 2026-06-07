#!/usr/bin/env bash
# Pick a gateway scrape target reachable from the Prometheus container.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${OOA_GATEWAY_PORT:-8000}"
TARGETS_FILE="monitoring/prometheus/targets/gateway.json"
CANDIDATES=(
  "host.docker.internal:${PORT}"
)

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [ -n "$LAN_IP" ]; then
  CANDIDATES+=("${LAN_IP}:${PORT}")
fi

pick=""
if docker info >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx ooa-prometheus; then
  for t in "${CANDIDATES[@]}"; do
    if docker exec ooa-prometheus wget -q --spider --timeout=4 "http://${t}/metrics" 2>/dev/null; then
      pick="$t"
      break
    fi
  done
else
  pick="host.docker.internal:${PORT}"
fi

if [ -z "$pick" ]; then
  pick="host.docker.internal:${PORT}"
  echo "[WARN] Could not probe from Prometheus — keeping default target (gateway must bind 0.0.0.0)"
fi

mkdir -p "$(dirname "$TARGETS_FILE")"
python3 -c "
import json, sys
target = sys.argv[1]
path = sys.argv[2]
payload = [{'targets': [target], 'labels': {'job': 'ooa-gateway'}}]
with open(path, 'w', encoding='utf-8') as f:
    json.dump(payload, f, indent=2)
    f.write('\n')
print(target)
" "$pick" "$TARGETS_FILE"

echo "Wrote ${TARGETS_FILE} → ${pick}"

if curl -sf -X POST http://127.0.0.1:9090/-/reload >/dev/null 2>&1; then
  echo "Prometheus config reloaded."
else
  echo "Reload Prometheus: curl -X POST http://127.0.0.1:9090/-/reload"
  echo "Or: docker compose -f docker-compose.monitoring.yml restart prometheus"
fi
