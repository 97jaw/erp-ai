#!/usr/bin/env bash
# Quick diagnostics when monitoring URLs refuse connections
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== OOA monitoring diagnostics =="
echo ""

echo "1) Docker Desktop"
if command -v docker >/dev/null 2>&1; then
  docker desktop status 2>/dev/null || echo "  (docker desktop status unavailable)"
  if docker info >/dev/null 2>&1; then
    echo "  docker info: OK"
  else
    echo "  docker info: FAIL — engine not reachable"
    echo "  Fix: open -a Docker && wait until 'docker desktop status' shows running"
    exit 1
  fi
else
  echo "  docker CLI not found"
  exit 1
fi

echo ""
echo "2) OOA containers (name / status / ports)"
docker ps -a --filter name=ooa- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1 || true

echo ""
echo "3) Host port listeners (9090 Prometheus, 3030 Grafana, 3100 Loki, 8000 gateway)"
for p in 9090 3030 3100 9093 8000; do
  if lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | head -1 | grep -q .; then
    lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | head -1 | sed "s/^/  :$p /"
  else
    echo "  :$p  (nothing listening)"
  fi
done

echo ""
echo "4) HTTP probes"
for url in \
  "http://127.0.0.1:9090/-/healthy" \
  "http://127.0.0.1:3030/api/health" \
  "http://127.0.0.1:3100/ready" \
  "http://127.0.0.1:9093/-/healthy" \
  "http://127.0.0.1:8000/health"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 "$url" 2>/dev/null || echo "000")
  echo "  $code  $url"
done

echo ""
echo "5) Grafana container (if present)"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx ooa-grafana; then
  docker port ooa-grafana 2>/dev/null || echo "  no published ports"
  docker logs ooa-grafana --tail 5 2>&1 | sed 's/^/  /'
else
  echo "  ooa-grafana not running"
fi

echo ""
echo "Done. If docker info is OK but ports are empty, run:"
echo "  docker compose -f docker-compose.monitoring.yml up -d --force-recreate"
echo "  bash scripts/start_gateway.sh   # separate terminal"
