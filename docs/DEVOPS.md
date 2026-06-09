# OOA DevOps Guide

Complete reference for building, deploying, and operating **Odoo Omni-Agent (OOA)** — local development through AWS EC2 production.

---

## Table of contents

1. [Architecture](#architecture)
2. [Ports & services](#ports--services)
3. [Repository layout (DevOps)](#repository-layout-devops)
4. [Local development](#local-development)
5. [Production image build](#production-image-build)
6. [AWS EC2 deployment](#aws-ec2-deployment)
7. [Deploy without ECR (docker save + scp)](#deploy-without-ecr-docker-save--scp)
8. [Environment variables](#environment-variables)
9. [Container access & operations](#container-access--operations)
10. [Updating a release](#updating-a-release)
11. [Database & migrations](#database--migrations)
12. [Health checks & verification](#health-checks--verification)
13. [Logs & debugging](#logs--debugging)
14. [Security groups & networking](#security-groups--networking)
15. [HTTPS options](#https-options)
16. [Troubleshooting](#troubleshooting)
17. [Current staging reference](#current-staging-reference)
18. [Full stack deployment (app + monitoring)](#full-stack-deployment-app--monitoring)
19. [Simplified deployment (day-to-day code updates)](#simplified-deployment-day-to-day-code-updates)

---

## Architecture

### Production (single-container stack on EC2)

```
Internet
   │
   ▼
EC2 (Ubuntu 24.04, linux/amd64)
   │
   ├── gateway container  :8000   ← React UI + FastAPI API + /health
   │       │
   │       ├── outbound → Odoo 14 @ odoo.elrace.com (XML-RPC / HTTPS)
   │       ├── outbound → Anthropic / OpenAI / ElevenLabs APIs
   │       └── internal → postgres:5432 (admin DB)
   │
   └── postgres container :5432   ← users, RBAC, telemetry (not exposed publicly)
```

**Production image contents:** React UI build + Python 3.11 gateway + all backend code in one container (`docker/Dockerfile.prod`).

### Local development (multi-service, legacy compose)

`docker-compose.yml` runs separate gateway / orchestrator / odoo_bridge services. Most day-to-day dev uses **venv + uvicorn** directly instead.

---

## Ports & services

| Service | Environment | Host port | Container port | Exposed publicly? | Purpose |
|---------|-------------|-----------|----------------|-------------------|---------|
| **Gateway (UI + API)** | Production EC2 | `8000` | `8000` | Yes (SG rule) | Web UI, REST API, SSE `/chat/stream`, `/health` |
| **Postgres (admin)** | Production EC2 | — | `5432` | No (Docker network only) | Auth, RBAC, telemetry, conversations |
| **Postgres (admin)** | Local dev | `5433` | `5432` | localhost only | `docker-compose.admin-db.yml` |
| **Gateway** | Local venv | `8000` | — | localhost | `uvicorn gateway.main:app --port 8000` |
| **React UI dev server** | Local | `3000` | — | localhost | `cd ooa-ui && npm start` (proxies to 8000) |

### Key API endpoints

| Path | Method | Auth | Notes |
|------|--------|------|-------|
| `/health` | GET | No | Liveness probe |
| `/auth/login` | POST | No | Body: `{"file_id": "2721"}` |
| `/chat` | POST | Bearer JWT | Standard chat |
| `/chat/stream` | POST | Bearer JWT | SSE streaming (entity confirm cards) |
| `/chat/intelligent` | POST | Bearer JWT | Debug/canary — full orchestration metadata |
| `/admin` | GET | Bearer JWT | Admin panel UI |

---

## Repository layout (DevOps)

```
odoo_ai_bridge/
├── docker/
│   ├── Dockerfile.prod          # Production single-container build
│   └── docker-entrypoint.sh     # Runs DB migrations on start
├── deploy/aws/
│   ├── docker-compose.prod.yml  # EC2 stack (gateway + postgres)
│   ├── .env.production.example  # Template — copy to .env.production
│   ├── scripts/
│   │   ├── build-and-push.sh    # Build amd64 + push to ECR
│   │   ├── deploy-on-ec2.sh     # Pull/load image + compose up
│   │   ├── load-image-on-ec2.sh # Load docker save tarball
│   │   └── ec2-user-data.sh     # EC2 launch bootstrap (Docker install)
│   └── artifacts/               # docker save tarballs (gitignored in prod use)
├── docker-compose.yml           # Legacy multi-service dev compose
├── docker-compose.admin-db.yml  # Local admin Postgres on :5433
├── .env.production              # Production secrets (NEVER commit)
└── requirements.txt             # Python deps (includes rapidfuzz, etc.)
```

---

## Local development

### Prerequisites

- Python 3.11+
- Node 20+ (for UI)
- Docker (optional, for Postgres)
- Odoo API key + AI API keys

### Setup

```bash
cd odoo_ai_bridge

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: ODOO_V14_*, ANTHROPIC_API_KEY, JWT_SECRET, OOA_DB_URL, etc.
```

### Admin database (local)

```bash
docker compose -f docker-compose.admin-db.yml up -d

# In .env:
# OOA_DB_URL=postgresql://postgres:devpassword@localhost:5433/ooa

python scripts/admin_db_migrate.py
python scripts/admin_db_create_super_admin.py
```

### Run gateway (backend)

```bash
source venv/bin/activate
uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
```

### Run UI (frontend, optional separate terminal)

```bash
cd ooa-ui
npm install
npm start
# Opens http://localhost:3000 — proxies API to :8000
```

### Run tests

```bash
pytest tests/ -q
pytest tests/core/test_entity_resolver_typos.py -q   # typo/fuzzy tests
```

---

## Production image build

**Important:** Build on Mac (arm64) with `--platform linux/amd64` for AWS EC2 x86 instances. Building without this causes `exec format error` on EC2.

### Build locally (no push)

```bash
cd odoo_ai_bridge

docker buildx build --platform linux/amd64 \
  -f docker/Dockerfile.prod \
  -t ooa-gateway:latest \
  . --load
```

### Tag convention

| Tag | Purpose |
|-----|---------|
| `ooa-gateway:latest` | Default local tag |
| `ooa-gateway:phase-10-hardening` | Phase 10 release |
| `ooa-gateway:typo-handling` | Typo/fuzzy entity resolver release |

### Build + push to ECR

```bash
# One-time AWS setup
aws configure
# or: aws sso login --profile your-profile

export AWS_REGION=me-south-1          # Bahrain (closest to UAE)
# Alternative if me-south-1 unavailable: eu-central-1

export ECR_REPO=ooa-gateway
export IMAGE_TAG=typo-handling        # your release tag

chmod +x deploy/aws/scripts/*.sh
./deploy/aws/scripts/build-and-push.sh
```

Script prints `OOA_IMAGE=<account>.dkr.ecr.<region>.amazonaws.com/ooa-gateway:<tag>` — set this in `.env.production` on EC2.

**IAM note:** If `ecr:CreateRepository` is denied, use the [docker save + scp](#deploy-without-ecr-docker-save--scp) path instead.

---

## AWS EC2 deployment

### Instance requirements

| Setting | Value |
|---------|-------|
| AMI | Ubuntu 24.04 LTS |
| Instance type | `t3.medium` minimum (2 vCPU, 4 GB RAM) |
| Architecture | **x86_64 (amd64)** |
| Storage | 30 GB gp3 |
| Region | `ap-south-1` (Mumbai) or `me-south-1` (Bahrain) |
| App path on server | `/opt/ooa` |

### EC2 bootstrap (user data)

Paste `deploy/aws/scripts/ec2-user-data.sh` into **Launch instance → Advanced → User data**. This installs Docker, Docker Compose plugin, git, and awscli.

### First-time server setup

```bash
# From your Mac
chmod 400 /path/to/your-key.pem
ssh -i /path/to/your-key.pem ubuntu@<EC2_PUBLIC_IP>

# On EC2
sudo mkdir -p /opt/ooa && sudo chown ubuntu:ubuntu /opt/ooa
cd /opt/ooa

# Option A: git clone
git clone <repo-url> .

# Option B: rsync from Mac (no git on server)
# rsync -avz --exclude venv --exclude node_modules --exclude .git \
#   -e "ssh -i /path/to/key.pem" \
#   ./odoo_ai_bridge/ ubuntu@<EC2_IP>:/opt/ooa/
```

### Configure secrets

```bash
cd /opt/ooa
cp deploy/aws/.env.production.example .env.production
nano .env.production
```

Required values — see [Environment variables](#environment-variables).

Generate secrets:

```bash
openssl rand -hex 32    # JWT_SECRET
openssl rand -base64 24 # POSTGRES_PASSWORD
```

Set image reference:

```bash
# ECR path:
OOA_IMAGE=682033490020.dkr.ecr.eu-central-1.amazonaws.com/ooa-gateway:typo-handling

# OR local loaded image (no ECR):
OOA_IMAGE=ooa-gateway:typo-handling
```

### Deploy stack

```bash
cd /opt/ooa
chmod +x deploy/aws/scripts/*.sh
./deploy/aws/scripts/deploy-on-ec2.sh
```

This script:
1. Logs into ECR (if `OOA_IMAGE` is an ECR URI)
2. Pulls the image (or builds on EC2 if `OOA_IMAGE` unset)
3. Runs `docker compose up -d`
4. Waits for `/health` to return 200

### Manual compose commands

All compose commands run from `/opt/ooa`:

```bash
COMPOSE="docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production"

$COMPOSE up -d                    # Start
$COMPOSE down                     # Stop
$COMPOSE ps                       # Status
$COMPOSE restart gateway          # Restart gateway only
$COMPOSE pull gateway && $COMPOSE up -d gateway   # Pull + recreate
```

---

## Deploy without ECR (docker save + scp)

Use when ECR push is blocked or for air-gapped deploys.

### On Mac (build machine)

```bash
cd odoo_ai_bridge

# Build for EC2 amd64
docker buildx build --platform linux/amd64 \
  -f docker/Dockerfile.prod \
  -t ooa-gateway:typo-handling \
  . --load

# Save (~2–2.5 GB compressed)
docker save ooa-gateway:typo-handling | gzip > deploy/aws/artifacts/ooa-gateway-typo-handling-amd64.tar.gz

# Copy to EC2
chmod 400 /path/to/elrace-ai.pem
scp -i /path/to/elrace-ai.pem \
  deploy/aws/artifacts/ooa-gateway-typo-handling-amd64.tar.gz \
  ubuntu@<EC2_IP>:/tmp/
```

### On EC2 (load + restart)

```bash
ssh -i /path/to/elrace-ai.pem ubuntu@<EC2_IP>

# Load image
gunzip -c /tmp/ooa-gateway-typo-handling-amd64.tar.gz | docker load
docker images ooa-gateway:typo-handling

# Point compose at loaded image
cd /opt/ooa
sed -i 's|^OOA_IMAGE=.*|OOA_IMAGE=ooa-gateway:typo-handling|' .env.production

# Restart gateway
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production up -d gateway

# Verify
curl -sf http://127.0.0.1:8000/health && echo OK
```

Or use the helper script:

```bash
./deploy/aws/scripts/load-image-on-ec2.sh /tmp/ooa-gateway-typo-handling-amd64.tar.gz
./deploy/aws/scripts/deploy-on-ec2.sh
```

---

## Environment variables

Copy from `deploy/aws/.env.production.example`. File lives at `/opt/ooa/.env.production` on EC2.

### Required

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Postgres password for compose service |
| `JWT_SECRET` | 256-bit random — invalidates all sessions if changed |
| `ODOO_V14_URL` | e.g. `https://odoo.elrace.com` |
| `ODOO_V14_DB` | e.g. `odoo.elrace.com` |
| `ODOO_V14_USER` | Odoo API user (e.g. `dev`) |
| `ODOO_V14_PASSWORD` | Odoo **API key** (not web login password) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ELEVENLABS_API_KEY` | TTS (optional but configured) |
| `OOA_IMAGE` | Docker image tag or full ECR URI |

### Auth / admin

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPER_ADMIN_FILE_ID` | `2721` | Elrace file ID for bootstrap super admin |
| `RBAC_ENFORCE` | `true` | Enforce role-based access |
| `JWT_ACCESS_HOURS` | `8` | Access token TTL |
| `JWT_REFRESH_DAYS` | `30` | Refresh token TTL |
| `AUTH_VERIFY_ODOO_ON_LOGIN` | `false` | Block login when Odoo verify fails and no cached identity |
| `AUTH_ODOO_SYNC_TTL_HOURS` | `24` | Skip Odoo employee re-verify on login when cache is fresh (`0` = always sync) |

### Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `OOA_HTTP_PORT` | `8000` | Host port mapped to gateway |
| `OOO_LOG_LEVEL` | `INFO` | Log verbosity |
| `OOA_LOG_JSON` | `true` (in compose) | Structured JSON logs |
| `ODOO_XMLRPC_TIMEOUT` | `600` | Odoo RPC timeout (seconds) |
| `SCHEMA_CACHE_DIR` | `.cache/schema` | Persisted in `ooa-cache` volume |

### Set automatically by compose

| Variable | Value |
|----------|-------|
| `OOA_DB_URL` | `postgresql://ooa:${POSTGRES_PASSWORD}@postgres:5432/ooa` |
| `OOA_GATEWAY_HOST` | `0.0.0.0` |
| `OOA_GATEWAY_PORT` | `8000` |

---

## Container access & operations

### Container names

After `docker compose up`, containers are prefixed by the compose project directory name (e.g. `aws-gateway-1`, `aws-postgres-1` when run from `deploy/aws/`, or similar when run from `/opt/ooa`).

Find running containers:

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production ps
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Shell into gateway container

```bash
COMPOSE="docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production"

# Interactive shell (runs as user `ooa`)
$COMPOSE exec gateway bash

# One-off command
$COMPOSE exec gateway python -c "import rapidfuzz; print(rapidfuzz.__version__)"
$COMPOSE exec gateway curl -sf http://127.0.0.1:8000/health
```

### Shell into Postgres container

```bash
$COMPOSE exec postgres psql -U ooa -d ooa

# Example queries
# \dt
# SELECT count(*) FROM users;
# SELECT id, file_id, name FROM users LIMIT 5;
```

### Docker volumes

| Volume | Mount in gateway | Purpose |
|--------|------------------|---------|
| `ooa-pg-data` | — | Postgres data (persistent) |
| `ooa-logs` | `/app/logs` | Application logs |
| `ooa-cache` | `/app/.cache` | Schema cache |

Inspect volumes:

```bash
docker volume ls | grep ooa
docker volume inspect <volume_name>
```

### Process inside gateway container

- **User:** `ooa` (non-root)
- **Workdir:** `/app`
- **Entrypoint:** `/docker-entrypoint.sh` → runs `admin_db_migrate.py` then starts uvicorn
- **CMD:** `uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --workers 1`

---

## Updating a release

### Path A — ECR

```bash
# Mac
export IMAGE_TAG=v1.0.2
./deploy/aws/scripts/build-and-push.sh

# EC2 — edit .env.production OOA_IMAGE tag, then:
cd /opt/ooa
./deploy/aws/scripts/deploy-on-ec2.sh
```

### Path B — docker save (current workflow)

```bash
# Mac: build amd64, save, scp (see section above)

# EC2:
gunzip -c /tmp/ooa-gateway-<tag>-amd64.tar.gz | docker load
sed -i 's|^OOA_IMAGE=.*|OOA_IMAGE=ooa-gateway:<tag>|' /opt/ooa/.env.production
docker compose -f /opt/ooa/deploy/aws/docker-compose.prod.yml \
  --env-file /opt/ooa/.env.production up -d gateway
```

### Rollback

```bash
# List loaded images
docker images ooa-gateway

# Switch tag in .env.production to previous tag, then:
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production up -d gateway
```

---

## Database & migrations

Migrations run **automatically** on every gateway container start via `docker/docker-entrypoint.sh`.

### Manual migration (if needed)

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway python scripts/admin_db_migrate.py
```

### Create / sync super admin

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway python scripts/admin_db_create_super_admin.py
```

### Migration files location

```
admin/db/migrations/
  001_initial.sql
  ...
  009_phase10_query_telemetry.sql
```

---

## Health checks & verification

### Quick checks

```bash
# On EC2
curl -sf http://127.0.0.1:8000/health | jq .

# From Mac (replace IP)
curl -sf http://<EC2_IP>:8000/health
```

Expected response:

```json
{"status":"ok","version":"3.0.0","model":"claude-sonnet-4-20250514"}
```

### Login test

```bash
curl -s -X POST http://<EC2_IP>:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"file_id":"2721"}' | jq .
```

### Entity resolution smoke test (typo handling)

```bash
# Requires jq — tests SSE /chat/stream
TOKEN=$(curl -s -X POST http://<EC2_IP>:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"file_id":"2721"}' | jq -r .access_token)

curl -s -N -X POST http://<EC2_IP>:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"show me zaidia boys school expenses","session_id":"test-1"}' \
  | grep -o '"label":"[^"]*"' | head -3
```

Expected top match: `Zayidia Boys School (WO: RCC-AA-MOE-2025-016)`.

### Acceptance scripts (from dev machine)

```bash
OOA_API_BASE=http://<EC2_IP>:8000 ./venv/bin/python scripts/phase3_live_acceptance.py
OOA_API_BASE=http://<EC2_IP>:8000 ./venv/bin/python scripts/phase4_acceptance.py
```

---

## Logs & debugging

### Follow gateway logs

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs -f gateway
```

### Follow all services

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs -f
```

### Last N lines

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs --tail=100 gateway
```

### Filter structured JSON logs

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs gateway 2>&1 \
  | grep EntityResolver

docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs gateway 2>&1 \
  | grep entity_gate
```

### Log files inside container

```bash
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway ls -la /app/logs/
```

---

## Security groups & networking

### Inbound (EC2 security group)

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP /32 | Admin access |
| Custom TCP | 8000 | Your IP or team CIDR | OOA UI + API (testing) |
| Custom TCP | 443 | 0.0.0.0/0 | HTTPS (when ALB/Caddy added) |

**Do not expose Postgres (5432) to the internet.**

### Outbound

Gateway needs outbound HTTPS to:

- `odoo.elrace.com` — Odoo XML-RPC
- `api.anthropic.com` — Claude
- `api.openai.com` — OpenAI
- `api.elevenlabs.io` — TTS (optional)

**Odoo firewall:** Whitelist the EC2 **public egress IP** (use an Elastic IP so the rule stays stable).

### SSH access

```bash
chmod 400 /path/to/key.pem
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_IP>
```

If `Permission denied (publickey)`: check key permissions (must be `400`), correct username (`ubuntu` on Ubuntu AMI), and that the key pair matches the instance.

---

## HTTPS options

| Option | Complexity | Notes |
|--------|------------|-------|
| **Application Load Balancer + ACM** | Medium | Production — terminate TLS at ALB, target group → EC2:8000 |
| **Caddy on EC2** | Low | Auto-TLS with domain A-record → Elastic IP |
| **Cloudflare** | Low | Orange-cloud proxy in front of EC2 |

Until HTTPS is configured, access via `http://<EC2_IP>:8000`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `exec format error` on EC2 | arm64 image on amd64 instance | Rebuild with `--platform linux/amd64` |
| Gateway unhealthy / restart loop | Migration failed, bad `OOA_DB_URL` | Check `docker compose logs gateway`; verify Postgres is healthy |
| `Connection refused` on :8000 | SG missing port 8000 rule | Add inbound rule; verify `docker compose ps` |
| Odoo auth / XML-RPC errors | Wrong API key, firewall | Verify `ODOO_V14_PASSWORD`; curl Odoo from EC2 |
| UI loads, API 401 | JWT expired or `JWT_SECRET` changed | Clear browser localStorage; re-login |
| Entity not found | Odoo unreachable from EC2 | `curl -I https://odoo.elrace.com` from EC2 |
| Slow first query | Cold schema cache | Normal — subsequent queries faster |
| `Permission denied` on .pem | Key permissions too open | `chmod 400 key.pem` |
| ECR push denied | Missing IAM permissions | Use docker save + scp path |
| ElevenLabs 401 in logs | Invalid/expired API key | Non-fatal — TTS may be unavailable |
| Image ~2.3 GB scp slow | Large layer | Expected; consider ECR once IAM fixed |

### Common diagnostic commands

```bash
# Container status
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production ps

# Gateway health from inside
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway curl -sf http://127.0.0.1:8000/health

# Disk space (images are large)
df -h
docker system df

# Clean old images (careful)
docker image prune -a
```

---

## Full stack deployment (app + monitoring)

For production use on EC2, deploy **both** the app and the monitoring stack (same as Docker Desktop on Mac).

### What runs on the server

| Layer | Containers | Required? |
|-------|------------|-----------|
| **App** | `gateway`, `postgres` | **Yes** — AI software |
| **Monitoring** | `prometheus`, `grafana`, `loki`, `promtail`, `alertmanager`, `redis`, exporters, `cadvisor`, `node_exporter` | Recommended for ops |
| **Portainer** | `portainer` | Optional — container UI |

After full deploy you should see **~13 containers** in Portainer (12 compose + Portainer).

### One-command deploy on EC2

```bash
cd /opt/ooa
./deploy/aws/scripts/deploy-full-stack.sh
```

This runs:
1. `scripts/render_alertmanager_config.py` (reads `.env.production`)
2. `docker compose -f deploy/aws/docker-compose.prod.yml -f deploy/aws/docker-compose.monitoring.prod.yml up -d`

### Security group ports (restrict to your IP)

| Port | Service |
|------|---------|
| 8000 | OOA app (UI + API) |
| 9443 | Portainer (HTTPS) |
| 3030 | Grafana dashboards |
| 9090 | Prometheus (optional) |
| 9093 | Alertmanager (optional) |

Do **not** expose exporter ports (9100, 9121, 9187, 8080) publicly unless needed for debugging.

### URLs (staging EC2)

| Service | URL |
|---------|-----|
| OOA app | http://13.203.223.70:8000 |
| Grafana | http://13.203.223.70:3030 (admin / password in `.env.production`) |
| Prometheus | http://13.203.223.70:9090 |
| Portainer | https://13.203.223.70:9443 |

### Mac vs server — why they differed before

| Mac Docker Desktop | EC2 (before) | EC2 (after full deploy) |
|--------------------|--------------|-------------------------|
| App + monitoring (~12 containers) | App only (3 containers) | App + monitoring (~13 with Portainer) |

Portainer only shows containers **on that server** — it never sees your Mac.

### Instance sizing

| Stack | Minimum instance |
|-------|------------------|
| App only | `t3.medium` (4 GB RAM) |
| App + monitoring | `t3.large` (8 GB RAM) recommended |

---

## Current staging reference

> Update this section when infrastructure changes.

| Item | Value |
|------|-------|
| **EC2 public IP** | `13.203.223.70` |
| **Region** | `ap-south-1` (Mumbai) |
| **SSH user** | `ubuntu` |
| **SSH key (Mac)** | `~/projects/ai/elrace-ai.pem` |
| **App directory** | `/opt/ooa` |
| **Compose file** | `/opt/ooa/deploy/aws/docker-compose.prod.yml` + `docker-compose.monitoring.prod.yml` |
| **Deploy script** | `./deploy/aws/scripts/deploy-full-stack.sh` |
| **Env file** | `/opt/ooa/.env.production` |
| **Current image** | `ooa-gateway:typo-handling` |
| **URL** | http://13.203.223.70:8000 |
| **AWS account** | `682033490020` |
| **ECR region (alternate)** | `eu-central-1` |
| **Odoo** | `https://odoo.elrace.com` |
| **Super admin file ID** | `2721` |

### One-liner SSH

```bash
ssh -i ~/projects/ai/elrace-ai.pem ubuntu@13.203.223.70
```

### One-liner redeploy (from Mac, after building image)

```bash
# Build + save + upload + restart (customize TAG)
TAG=typo-handling
EC2=13.203.223.70
KEY=~/projects/ai/elrace-ai.pem

docker buildx build --platform linux/amd64 -f docker/Dockerfile.prod -t ooa-gateway:$TAG . --load
docker save ooa-gateway:$TAG | gzip > /tmp/ooa-$TAG-amd64.tar.gz
scp -i $KEY /tmp/ooa-$TAG-amd64.tar.gz ubuntu@$EC2:/tmp/
ssh -i $KEY ubuntu@$EC2 "gunzip -c /tmp/ooa-$TAG-amd64.tar.gz | docker load && \
  sed -i 's|^OOA_IMAGE=.*|OOA_IMAGE=ooa-gateway:$TAG|' /opt/ooa/.env.production && \
  docker compose -f /opt/ooa/deploy/aws/docker-compose.prod.yml --env-file /opt/ooa/.env.production up -d gateway && \
  curl -sf http://127.0.0.1:8000/health && echo OK"
```

---

## Future production hardening

- Move Postgres to **Amazon RDS** (remove compose postgres service)
- Deploy gateway on **ECS Fargate** behind ALB
- Restrict SG port 8000 to office VPN / ALB only
- Enable **AWS CloudWatch** log driver for containers
- Set up CI/CD (GitHub Actions → ECR → EC2/ECS)
- Department/module RBAC via `/admin` panel (`admin/rbac/`)

---

## Simplified deployment (day-to-day code updates)

Use this workflow every time you change code and want it live on the server.

### Important — do NOT git pull inside the container

Code is **baked into the Docker image** at `/app`. The gateway container:

- Has **no git** installed
- Loses any manual edits on **restart**

| Wrong | Right |
|-------|-------|
| Portainer → `aws-gateway-1` → Console → `git pull` | SSH to EC2 → `cd /opt/ooa` → `git pull` on the **host** |
| Edit files in `/app` inside the container | Rebuild the image after pulling on the host |

The Portainer terminal on `aws-gateway-1` (port 8000) is for **debugging only** — not for deploying code.

---

### Step 1 — Push from your Mac

```bash
cd /Users/mjawad/projects/ai/odoo_ai_bridge/odoo_ai_bridge

git add .
git commit -m "describe your change"
git push
```

---

### Step 2 — Pull on the EC2 host (not inside the container)

```bash
ssh -i ~/projects/ai/elrace-ai.pem ubuntu@13.203.223.70

cd /opt/ooa          # ← pull HERE (host path)
git pull
```

**Deploy path on server:** `/opt/ooa`  
**App path inside container (read-only for deploy):** `/app`

---

### Step 3 — Rebuild image and restart gateway

`git pull` on the host updates files on disk but **does not** update the running container. You must rebuild or load a new image.

**Option A — Rebuild on EC2** (simplest when the repo is cloned at `/opt/ooa`):

```bash
cd /opt/ooa

docker buildx build --platform linux/amd64 \
  -f docker/Dockerfile.prod \
  -t ooa-gateway:typo-handling \
  .

docker compose -f deploy/aws/docker-compose.prod.yml \
  --env-file .env.production up -d gateway

curl -sf http://127.0.0.1:8000/health && echo OK
```

**Option B — Build on Mac, upload image** (faster if EC2 build is slow):

```bash
# On Mac — see "One-liner redeploy" under Current staging reference
TAG=typo-handling
EC2=13.203.223.70
KEY=~/projects/ai/elrace-ai.pem

docker buildx build --platform linux/amd64 -f docker/Dockerfile.prod -t ooa-gateway:$TAG . --load
docker save ooa-gateway:$TAG | gzip > /tmp/ooa-$TAG-amd64.tar.gz
scp -i $KEY /tmp/ooa-$TAG-amd64.tar.gz ubuntu@$EC2:/tmp/
ssh -i $KEY ubuntu@$EC2 "gunzip -c /tmp/ooa-$TAG-amd64.tar.gz | docker load && \
  sed -i 's|^OOA_IMAGE=.*|OOA_IMAGE=ooa-gateway:$TAG|' /opt/ooa/.env.production && \
  docker compose -f /opt/ooa/deploy/aws/docker-compose.prod.yml --env-file /opt/ooa/.env.production up -d gateway && \
  curl -sf http://127.0.0.1:8000/health && echo OK"
```

**Monitoring-only changes** (Grafana/Prometheus configs, no gateway code):

```bash
cd /opt/ooa
git pull
./deploy/aws/scripts/deploy-full-stack.sh
```

---

### Step 4 — Restart only (no code change)

If you only need a restart (config reload, stuck process):

**From EC2:**

```bash
docker compose -f deploy/aws/docker-compose.prod.yml \
  --env-file .env.production restart gateway
```

**From Portainer:**

1. Open https://13.203.223.70:9443
2. **Containers** → `aws-gateway-1`
3. Click **Restart**

No `git pull` needed for a restart-only action.

---

### Container terminal (debugging only)

In Portainer → `aws-gateway-1` → **Console** → command `/bin/bash` → **Connect**:

```bash
cd /app
curl -sf http://127.0.0.1:8000/health
ls -la
python -c "import gateway; print('ok')"
```

Use this to inspect logs, test imports, or verify health — **not** to pull code or edit production files.

---

### Quick cheat sheet

| Step | Where | Command |
|------|--------|---------|
| Push code | Mac | `git push` |
| Pull code | EC2 **host** | `cd /opt/ooa && git pull` |
| Deploy new code | EC2 **host** | Rebuild image → `docker compose ... up -d gateway` |
| Restart app only | Portainer or EC2 | Restart `aws-gateway-1` |
| Debug shell | Portainer → `aws-gateway-1` → Console | `/bin/bash` → work in `/app` |
| Full stack (app + monitoring) | EC2 **host** | `./deploy/aws/scripts/deploy-full-stack.sh` |

**Summary:** Push on Mac → pull in `/opt/ooa` on the server → rebuild image → restart gateway.

---

*Last updated: June 2026 — covers typo-handling release (`ooa-gateway:typo-handling`).*
