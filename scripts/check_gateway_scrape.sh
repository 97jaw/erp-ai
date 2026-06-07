#!/usr/bin/env bash
# Verify Prometheus (inside Docker) can scrape the gateway on the host.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${OOA_GATEWAY_PORT:-8000}"
HOST_BIND="${OOA_GATEWAY_HOST:-0.0.0.0}"

echo "== Gateway scrape check (Prometheus → host:${PORT}) =="
echo ""

if ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | grep -q .; then
  echo "[FAIL] Nothing listening on port $PORT"
  echo "       Start: bash scripts/start_gateway.sh"
  exit 1
fi

echo "Listener on :$PORT:"
lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -3 | sed 's/^/  /'

echo ""
echo "Host probes:"
for url in "http://127.0.0.1:${PORT}/health" "http://127.0.0.1:${PORT}/metrics"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo "000")
  echo "  $code  $url"
done

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [ -n "$LAN_IP" ]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://${LAN_IP}:${PORT}/health" 2>/dev/null || echo "000")
  echo "  $code  http://${LAN_IP}:${PORT}/health  (Docker host usually needs this to work)"
  if [ "$code" != "200" ]; then
    echo ""
    echo "[FIX] Gateway is likely bound to 127.0.0.1 only."
    echo "      Restart with all interfaces:"
    echo "        lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true"
    echo "        OOA_GATEWAY_HOST=0.0.0.0 bash scripts/start_gateway.sh"
    exit 1
  fi
fi

echo ""
if ! docker info >/dev/null 2>&1; then
  echo "[SKIP] Docker not running — cannot test from Prometheus container"
  exit 0
fi

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx ooa-prometheus; then
  echo "[SKIP] ooa-prometheus not running"
  exit 0
fi

echo "From ooa-prometheus container (host.docker.internal):"
if docker exec ooa-prometheus wget -qO- --timeout=5 "http://host.docker.internal:${PORT}/metrics" 2>/dev/null | head -1 | grep -q '^#'; then
  echo "  [OK]   Prometheus can scrape /metrics"
  echo ""
  echo "Reload Prometheus config (if target was just fixed):"
  echo "  curl -X POST http://127.0.0.1:9090/-/reload"
  exit 0
fi

echo "  [FAIL] Cannot reach host.docker.internal:${PORT}/metrics"
echo ""
echo "Try:"
echo "  1. OOA_GATEWAY_HOST=0.0.0.0 bash scripts/start_gateway.sh"
echo "  2. ./scripts/set_prometheus_gateway_target.sh"
echo "  3. curl -X POST http://127.0.0.1:9090/-/reload"
exit 1
