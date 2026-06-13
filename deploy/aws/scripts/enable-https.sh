#!/usr/bin/env bash
# Enable HTTPS in front of OOA gateway (for microphone / secure context).
#
# Run ON EC2 from repo root (/opt/ooa):
#   chmod +x deploy/aws/scripts/enable-https.sh
#
# Option A — URGENT, no domain (self-signed cert, accept browser warning):
#   ./deploy/aws/scripts/enable-https.sh
#
# Option B — Production (Let's Encrypt; DNS A record must point to this server):
#   OOA_DOMAIN=ooa.yourdomain.com ./deploy/aws/scripts/enable-https.sh
#
# Then open https://<EC2_IP> or https://<OOA_DOMAIN> (not http://...:8000).
# AWS security group: allow inbound TCP 443 (and 80 for ACME redirect if using a domain).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DEPLOY="${ROOT}/deploy/aws"
COMPOSE="-f ${DEPLOY}/docker-compose.prod.yml -f ${DEPLOY}/docker-compose.live.yml -f ${DEPLOY}/docker-compose.https.yml"
ENV_FILE="${ROOT}/.env.production"
CADDYFILE="${DEPLOY}/Caddyfile"
DOMAIN="${OOA_DOMAIN:-}"

cd "${ROOT}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

if [[ -n "${DOMAIN}" ]]; then
  echo "==> Writing Caddyfile for domain: ${DOMAIN}"
  cat > "${CADDYFILE}" <<EOF
${DOMAIN} {
	encode gzip
	reverse_proxy gateway:8000
}
EOF
else
  echo "==> Writing self-signed Caddyfile (no OOA_DOMAIN set)"
  PUBLIC_IP="$(curl -fsS http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || curl -fsS https://checkip.amazonaws.com 2>/dev/null || true)"
  if [[ -n "${PUBLIC_IP}" ]]; then
    cat > "${CADDYFILE}" <<EOF
{
	auto_https disable_redirects
}

https://${PUBLIC_IP} {
	tls internal
	encode gzip
	reverse_proxy gateway:8000
}
EOF
  else
    cp "${DEPLOY}/Caddyfile.selfsigned" "${CADDYFILE}"
  fi
fi

PUBLIC_IP="$(curl -fsS http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"

echo "==> Starting Caddy + gateway"
docker compose ${COMPOSE} --env-file "${ENV_FILE}" up -d gateway caddy

echo "==> Waiting for Caddy..."
sleep 3
if curl -kfsS "https://127.0.0.1/health" >/dev/null 2>&1; then
  echo "OK — HTTPS proxy healthy (self-signed: curl -k)"
elif [[ -n "${PUBLIC_IP:-}" ]] && curl -kfsS "https://${PUBLIC_IP}/health" >/dev/null 2>&1; then
  echo "OK — HTTPS proxy healthy at https://${PUBLIC_IP}"
elif curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
  echo "WARN — Caddy up but HTTPS health check failed; check: docker compose logs caddy"
else
  echo "WARN — health check failed; logs:"
  docker compose ${COMPOSE} --env-file "${ENV_FILE}" logs --tail=30 caddy
  exit 1
fi

echo ""
echo "Done."
if [[ -n "${DOMAIN}" ]]; then
  echo "  Open: https://${DOMAIN}"
else
  echo "  Open: https://${PUBLIC_IP:-<EC2_PUBLIC_IP>}"
  echo "  Accept the browser security warning once (self-signed cert)."
fi
echo "  Microphone requires this HTTPS URL — not http://...:8000"
echo "  Ensure AWS SG allows inbound TCP 443."
