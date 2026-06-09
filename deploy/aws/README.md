# OOA — Deploy to AWS

Single-container deployment: **React UI + FastAPI gateway + PostgreSQL (admin/RBAC)**.

Recommended first path: **EC2 + ECR + Docker Compose** (fast to test). Move to ECS Fargate + RDS when you harden for production.

---

## Architecture

```
Internet → EC2 (Docker)
              ├── gateway:8000  (UI + API + /health)
              └── postgres:5432 (admin DB — users, RBAC, telemetry)
                    ↓
              Odoo 14 @ odoo.elrace.com (XML-RPC, outbound HTTPS)
              Anthropic / OpenAI / ElevenLabs APIs
```

Future work (you mentioned): department/module access for super admin → already partially in `admin/rbac/`; admin panel UI at `/admin` once deployed.

---

## Prerequisites

| Item | Notes |
|------|--------|
| AWS account | IAM user or SSO with ECR + EC2 permissions |
| AWS CLI | `aws configure` or `aws login` |
| Docker | Local Mac for build/push |
| Odoo API key | Same as dev — not the web password |
| AI API keys | Anthropic, OpenAI, ElevenLabs |

**Region:** `me-south-1` (Bahrain) is closest to UAE. Use `eu-central-1` if `me-south-1` is unavailable in your account.

**Odoo firewall:** Ensure `odoo.elrace.com` allows HTTPS/XML-RPC from your EC2 **public egress IP** (Elastic IP recommended).

---

## Step 1 — Build and push to ECR (local Mac)

```bash
cd odoo_ai_bridge

# Configure AWS (once)
aws configure
# or: aws sso login --profile your-profile

export AWS_REGION=me-south-1
export ECR_REPO=ooa-gateway
export IMAGE_TAG=phase-10-hardening   # optional

chmod +x deploy/aws/scripts/*.sh
./deploy/aws/scripts/build-and-push.sh
```

Note the printed `OOA_IMAGE=....amazonaws.com/ooa-gateway:tag` — you need it on EC2.

---

## Step 2 — Launch EC2

**Console → EC2 → Launch instance**

| Setting | Value |
|---------|--------|
| AMI | Ubuntu 24.04 LTS |
| Instance type | `t3.medium` (2 vCPU, 4 GB) minimum |
| Storage | 30 GB gp3 |
| Key pair | Create or select |
| Security group | See below |

**User data:** paste contents of `deploy/aws/scripts/ec2-user-data.sh` (installs Docker).

**Security group (testing)**

| Type | Port | Source |
|------|------|--------|
| SSH | 22 | Your IP |
| Custom TCP | 8000 | Your IP (or 0.0.0.0/0 for wider test — tighten later) |

**Optional:** attach an **Elastic IP** so Odoo firewall rules stay stable.

**IAM role for EC2** (recommended for ECR pull without static keys):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

Attach policy `AmazonEC2ContainerRegistryReadOnly` or the custom policy above.

---

## Step 3 — Configure secrets on EC2

SSH to the instance:

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Clone or copy the repo:

```bash
sudo mkdir -p /opt/ooa && sudo chown ubuntu:ubuntu /opt/ooa
cd /opt/ooa
git clone <your-repo-url> .
# or: scp -r odoo_ai_bridge/* ubuntu@<ip>:/opt/ooa/
```

Create production env file (never commit):

```bash
cp deploy/aws/.env.production.example .env.production
nano .env.production
```

**Required edits:**

- `POSTGRES_PASSWORD` — strong random password
- `JWT_SECRET` — `openssl rand -hex 32`
- `ODOO_V14_PASSWORD` — Odoo API key
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`
- `OOA_IMAGE=<full ECR URI from Step 1>`

---

## Step 4 — Deploy on EC2

```bash
cd /opt/ooa
chmod +x deploy/aws/scripts/*.sh
./deploy/aws/scripts/deploy-on-ec2.sh
```

Verify:

```bash
curl http://127.0.0.1:8000/health
# Open in browser: http://<EC2_PUBLIC_IP>:8000
```

Login with your Elrace **File ID** (e.g. `2721` for super admin dev account).

---

## Step 5 — Post-deploy

```bash
# Logs
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production logs -f gateway

# Migrations (also run automatically on container start)
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway python scripts/admin_db_migrate.py

# Sync super admin from env
docker compose -f deploy/aws/docker-compose.prod.yml --env-file .env.production \
  exec gateway python scripts/admin_db_create_super_admin.py
```

---

## HTTPS (recommended before wider access)

Option A — **Application Load Balancer + ACM certificate** (production)

Option B — **Caddy on EC2** reverse proxy (quick staging):

```bash
# Install Caddy, point domain A-record to Elastic IP, auto-TLS
```

Option C — **Cloudflare** in front of EC2 (orange cloud + SSL flexible/full)

---

## Fast deploy (git pull + restart — no docker build)

For day-to-day **Python/gateway** changes, mount `/opt/ooa` into the container so code updates do not require rebuilding the image.

### One-time setup on EC2

```bash
cd /opt/ooa
git pull   # includes deploy/aws/docker-compose.live.yml

# UI build folder is gitignored — copy it once from the running image:
docker cp aws-gateway-1:/app/ooa-ui/build ooa-ui/build

chmod +x deploy/aws/scripts/deploy-code.sh

# Recreate gateway with live mount (once):
docker compose -f deploy/aws/docker-compose.prod.yml \
  -f deploy/aws/docker-compose.live.yml \
  --env-file .env.production up -d gateway

curl -sf http://127.0.0.1:8000/health && echo OK
```

Keep `OOA_IMAGE` pointing at your existing runtime image (e.g. `ooa-gateway:typo-handling`). That image supplies Python deps; host disk supplies live code.

### Every deploy after that

**Mac:**
```bash
git push
```

**EC2:**
```bash
cd /opt/ooa
./deploy/aws/scripts/deploy-code.sh
```

Or manually: `git pull` then `docker compose -f deploy/aws/docker-compose.prod.yml -f deploy/aws/docker-compose.live.yml --env-file .env.production restart gateway`

### When you still need extra steps

| Change | Action |
|--------|--------|
| Python only (`gateway/`, `tests/`) | pull + restart (above) |
| React UI (`ooa-ui/src/`) | on EC2: `cd ooa-ui && npm ci && npm run build`, then restart |
| `requirements.txt` | rebuild base image once, or `docker compose exec gateway pip install -r requirements.txt` |
| Dockerfile / OS packages | full `docker build` + recreate container |

---

## Updating a release (full image rebuild)

Local:

```bash
export IMAGE_TAG=v1.0.1
./deploy/aws/scripts/build-and-push.sh
```

EC2 — update `OOA_IMAGE` tag in `.env.production`, then:

```bash
./deploy/aws/scripts/deploy-on-ec2.sh
```

---

## RDS instead of container Postgres (production)

When ready, replace the `postgres` service with Amazon RDS PostgreSQL 15:

```
OOA_DB_URL=postgresql://ooa:PASSWORD@your-rds.xxxx.me-south-1.rds.amazonaws.com:5432/ooa?sslmode=require
```

Remove `postgres` service from compose or use a `docker-compose.override` with gateway only.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `Migration failed` | Postgres up? `docker compose ps` |
| Odoo auth errors | API key, firewall, `ODOO_V14_URL` |
| UI loads but API 401 | JWT_SECRET changed? Clear browser localStorage |
| Entity gate not found | Odoo reachable from EC2: `curl -I https://odoo.elrace.com` |
| Slow first query | Normal — schema cache cold start |

---

## Future: admin panel access control

Planned (your roadmap):

- Module-level permissions per department (`admin/rbac/model_permissions.py`)
- Super admin configures user access in `/admin`
- Odoo-side record rules synced via `admin/db/migrations/006_odoo_module_permissions.sql`

Deploy this stack first; RBAC enforcement is already gated by `RBAC_ENFORCE=true` in `.env.production`.
