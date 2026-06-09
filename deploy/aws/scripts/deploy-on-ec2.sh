#!/usr/bin/env bash
# Run ON the EC2 instance after copying .env.production and compose files.
#
# Usage (on EC2, from repo root or /opt/ooa):
#   ./deploy/aws/scripts/deploy-on-ec2.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE_FILE="${ROOT}/deploy/aws/docker-compose.prod.yml"
ENV_FILE="${ROOT}/.env.production"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy deploy/aws/.env.production.example and fill secrets." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

if [[ -n "${OOA_IMAGE:-}" ]]; then
  REGION="${AWS_REGION:-me-south-1}"
  ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
  if [[ -n "${ACCOUNT}" && "${OOA_IMAGE}" == *".dkr.ecr."* ]]; then
    echo "==> ECR login..."
    aws ecr get-login-password --region "${REGION}" \
      | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
  fi
  echo "==> Pulling ${OOA_IMAGE}..."
  docker pull "${OOA_IMAGE}"
else
  echo "==> OOA_IMAGE not set — building locally on EC2 (slow first time)..."
fi

cd "${ROOT}"
export OOA_ENV_FILE="${ENV_FILE}"

echo "==> Starting stack..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --remove-orphans

echo "==> Waiting for health..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${OOA_HTTP_PORT:-8000}/health" >/dev/null; then
    echo "Gateway healthy on port ${OOA_HTTP_PORT:-8000}"
    exit 0
  fi
  sleep 2
done

echo "Health check timed out — inspect logs:" >&2
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs --tail=80 gateway
exit 1
