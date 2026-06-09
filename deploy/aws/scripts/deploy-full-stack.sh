#!/usr/bin/env bash
# Deploy OOA full stack on EC2: app (gateway + postgres) + monitoring + Portainer stays separate.
#
# Run ON EC2 from repo root (/opt/ooa):
#   ./deploy/aws/scripts/deploy-full-stack.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ENV_FILE="${ROOT}/.env.production"
COMPOSE_APP="${ROOT}/deploy/aws/docker-compose.prod.yml"
COMPOSE_MON="${ROOT}/deploy/aws/docker-compose.monitoring.prod.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy deploy/aws/.env.production.example and fill secrets." >&2
  exit 1
fi

# shellcheck disable=SC1090
# Do NOT `source` .env.production — values with spaces break bash.
export OOA_ENV_FILE="${ENV_FILE}"

cd "${ROOT}"

echo "==> Rendering Alertmanager config from .env.production..."
python3 scripts/render_alertmanager_config.py

if [[ ! -f monitoring/alertmanager/alertmanager.generated.yml ]]; then
  echo "Alertmanager config not generated — check scripts/render_alertmanager_config.py" >&2
  exit 1
fi

if [[ -n "${OOA_IMAGE:-}" && "${OOA_IMAGE}" == *".dkr.ecr."* ]]; then
  REGION="${AWS_REGION:-me-south-1}"
  ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
  if [[ -n "${ACCOUNT}" ]]; then
    echo "==> ECR login..."
    aws ecr get-login-password --region "${REGION}" \
      | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
    echo "==> Pulling ${OOA_IMAGE}..."
    docker pull "${OOA_IMAGE}"
  fi
fi

echo "==> Starting full stack (app + monitoring)..."
docker compose \
  -f "${COMPOSE_APP}" \
  -f "${COMPOSE_MON}" \
  --env-file "${ENV_FILE}" \
  up -d --remove-orphans

echo "==> Waiting for gateway health..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${OOA_HTTP_PORT:-8000}/health" >/dev/null; then
    break
  fi
  sleep 2
done

echo ""
echo "==> Container status:"
docker compose -f "${COMPOSE_APP}" -f "${COMPOSE_MON}" --env-file "${ENV_FILE}" ps

echo ""
echo "==> URLs (add EC2 security group rules for your IP first):"
echo "  OOA app:       http://<EC2_IP>:${OOA_HTTP_PORT:-8000}"
echo "  Grafana:       http://<EC2_IP>:${OOA_GRAFANA_PORT:-3030}  (admin / see GRAFANA_ADMIN_PASSWORD)"
echo "  Prometheus:    http://<EC2_IP>:${OOA_PROMETHEUS_PORT:-9090}"
echo "  Portainer:     https://<EC2_IP>:9443"
echo ""
echo "Done."
