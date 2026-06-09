#!/usr/bin/env bash
# Fast deploy: pull latest code and restart gateway (no docker build).
#
# Run on EC2 from repo root (/opt/ooa):
#   ./deploy/aws/scripts/deploy-code.sh
#
# Requires one-time setup with docker-compose.live.yml (see deploy/aws/README.md).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE="-f ${ROOT}/deploy/aws/docker-compose.prod.yml -f ${ROOT}/deploy/aws/docker-compose.live.yml"
ENV_FILE="${ROOT}/.env.production"

cd "${ROOT}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

echo "==> git pull"
git pull

echo "==> restart gateway (live mount reads /opt/ooa)"
docker compose ${COMPOSE} --env-file "${ENV_FILE}" restart gateway

echo "==> health check"
for _ in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:${OOA_HTTP_PORT:-8000}/health" >/dev/null 2>&1; then
    echo "OK — gateway healthy"
    exit 0
  fi
  sleep 2
done

echo "Health check failed — logs:" >&2
docker compose ${COMPOSE} --env-file "${ENV_FILE}" logs --tail=50 gateway
exit 1
