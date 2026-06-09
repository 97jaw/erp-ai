#!/usr/bin/env bash
# Load a docker save archive on EC2 (when ECR push is not available).
#
# On Mac (already done):
#   docker save ooa-gateway:phase-10-hardening | gzip > deploy/aws/artifacts/ooa-gateway-phase-10-hardening.tar.gz
#   scp -i key.pem deploy/aws/artifacts/ooa-gateway-phase-10-hardening.tar.gz ubuntu@<EC2_IP>:/tmp/
#
# On EC2:
#   ./deploy/aws/scripts/load-image-on-ec2.sh /tmp/ooa-gateway-phase-10-hardening.tar.gz

set -euo pipefail

ARCHIVE="${1:-/tmp/ooa-gateway-phase-10-hardening.tar.gz}"
if [[ ! -f "${ARCHIVE}" ]]; then
  echo "Archive not found: ${ARCHIVE}" >&2
  exit 1
fi

echo "==> Loading image from ${ARCHIVE}..."
gunzip -c "${ARCHIVE}" | docker load
docker images ooa-gateway:phase-10-hardening
echo "Done. Ensure .env.production has: OOA_IMAGE=ooa-gateway:phase-10-hardening"
