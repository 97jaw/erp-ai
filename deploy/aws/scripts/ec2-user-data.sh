#!/bin/bash
# EC2 user-data bootstrap — Ubuntu 22.04 / 24.04
# Paste into "Advanced details → User data" when launching the instance.
#
# After launch, SSH in and:
#   1. Clone repo or copy .env.production to /opt/ooa
#   2. Run deploy/aws/scripts/deploy-on-ec2.sh

set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl git awscli

# Docker Engine + Compose plugin
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

usermod -aG docker ubuntu || true

mkdir -p /opt/ooa
chown ubuntu:ubuntu /opt/ooa

# Allow Odoo XML-RPC + HTTPS outbound (default SG still needs inbound 8000 or 443)
echo "Bootstrap complete. Clone OOA to /opt/ooa and run deploy-on-ec2.sh" > /var/log/ooa-bootstrap.log
