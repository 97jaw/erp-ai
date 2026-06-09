#!/usr/bin/env bash
# Build OOA production image and push to Amazon ECR.
#
# Prerequisites:
#   aws configure   (or AWS SSO)
#   docker
#
# Usage:
#   export AWS_REGION=me-south-1          # Bahrain — closest to UAE
#   export ECR_REPO=ooa-gateway
#   ./deploy/aws/scripts/build-and-push.sh
#
# Optional:
#   IMAGE_TAG=phase-10-hardening ./deploy/aws/scripts/build-and-push.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
AWS_REGION="${AWS_REGION:-me-south-1}"
ECR_REPO="${ECR_REPO:-ooa-gateway}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "==> Account: ${ACCOUNT_ID}"
echo "==> Region:  ${AWS_REGION}"
echo "==> Image:   ${ECR_URI}:${IMAGE_TAG}"

if ! aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "==> Creating ECR repository ${ECR_REPO}..."
  aws ecr create-repository \
    --repository-name "${ECR_REPO}" \
    --image-scanning-configuration scanOnPush=true \
    --region "${AWS_REGION}" \
    --output text >/dev/null
fi

echo "==> Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Building production image (linux/amd64 for AWS EC2)..."
docker buildx build --platform linux/amd64 \
  -f "${ROOT}/docker/Dockerfile.prod" \
  -t "${ECR_REPO}:${IMAGE_TAG}" \
  "${ROOT}" \
  --load

echo "==> Tagging and pushing..."
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

echo ""
echo "Done. Set in .env.production:"
echo "  OOA_IMAGE=${ECR_URI}:${IMAGE_TAG}"
echo ""
echo "Deploy on EC2:"
echo "  ./deploy/aws/scripts/deploy-on-ec2.sh"
