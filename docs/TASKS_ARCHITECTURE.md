# TASKS — Architecture, Infrastructure & DevOps

> Server, database, deployment, and architectural tasks. For features see `TASKS_FEATURES.md`.

---

## Status Legend

```
✅ DONE       — Complete and operational
🔄 IN PROGRESS — Currently being worked on
📋 TODO       — Planned, not started
⚠️ CRITICAL   — Production risk, must address
🔒 SECURITY   — Security-related
```

---

## ✅ COMPLETED INFRASTRUCTURE

### Application Stack
- [x] FastAPI gateway with async support
- [x] Docker containerization
- [x] Environment-based configuration (.env)
- [x] CORS middleware for frontend access
- [x] In-memory `ConversationStore` with TTL
- [x] Cached Odoo adapter (singleton pattern)
- [x] Custom AI gateway methods in Odoo module
- [x] GitHub repository setup
- [x] Local development environment (Mac M5)

### Performance Optimizations Done
- [x] Adapter authentication caching (no re-auth per request)
- [x] Tool result truncation for large reports (50KB limit)
- [x] Streaming responses via SSE
- [x] Visualization payload separated from text

---

## ⚠️ CRITICAL — Priority 1

### Production Server Setup (Server 2)

**Problem:** AI queries cause 700%+ CPU spikes on production Odoo server, impacting real users.

**Solution:** Separate read replica architecture.

#### Phase 1.1 — Server 2 Provisioning
- [ ] Provision Hetzner CX22 VPS (2 vCPU, 4GB RAM, ~$6/month)
- [ ] Location: Nuremberg (closest to UAE)
- [ ] OS: Ubuntu 22.04 LTS
- [ ] Configure SSH key access
- [ ] Set up firewall (ufw) — allow 22, 80, 443, 8000
- [ ] Install Docker, Git, Nano

#### Phase 1.2 — PostgreSQL Read Replica
- [ ] Configure streaming replication from Odoo primary
- [ ] Set `wal_level = replica` on primary
- [ ] Create `replicator` user on primary
- [ ] Update `pg_hba.conf` to allow replica connection
- [ ] Run `pg_basebackup` on Server 2
- [ ] Configure standby signal and `primary_conninfo`
- [ ] Verify replication via `pg_stat_replication`
- [ ] Create `ai_reader` read-only user on replica
- [ ] Test query: `SELECT count(*) FROM account_move_line`
- [ ] Measure replica lag (target: < 2 seconds)

#### Phase 1.3 — Redis Cache Layer
- [ ] Install Redis on Server 2
- [ ] Configure: `maxmemory 512mb`, `allkeys-lru` policy
- [ ] Bind to 127.0.0.1 only (security)
- [ ] Add `redis` Python library to requirements
- [ ] Implement `ResponseCache` class in gateway
- [ ] Add TTL config per tool (5min reports, 1min searches)
- [ ] Add cache key hashing (md5 of tool name + params)
- [ ] Add `/cache` DELETE endpoint for manual flush
- [ ] Add cache hit/miss logging

#### Phase 1.4 — Direct SQL Bypass
- [ ] Add `psycopg2-binary` to requirements
- [ ] Implement `get_pg_connection()` helper
- [ ] Write `sql_get_pandl()` — direct SQL P&L query
- [ ] Write `sql_get_balance_sheet()` — direct SQL Balance Sheet
- [ ] Write `sql_get_trial_balance()` — direct SQL Trial Balance
- [ ] Update `execute_tool()` to prefer SQL when `PG_HOST` is set
- [ ] Fallback to XML-RPC gateway methods if SQL fails
- [ ] Compare SQL results vs Odoo UI numbers — 100% match required
- [ ] Add statement timeout (30s) on PG connection

#### Phase 1.5 — OOA Deployment to Server 2
- [ ] Clone repo to `/opt/ooa`
- [ ] Create production `.env` with all keys + PG_HOST + REDIS_URL
- [ ] Build Docker image: `docker build -t ooa:prod .`
- [ ] Run as systemd service for auto-restart
- [ ] Set up Nginx reverse proxy
- [ ] Configure SSL via Let's Encrypt (certbot)
- [ ] Update `.env` URLs in React UI to point to production
- [ ] Update CORS allowed origins to production domain
- [ ] Test end-to-end with real Elrace data

---

## 📋 Priority 2 — Reliability & Scaling

### Session Persistence
- [ ] Move `ConversationStore` from in-memory to PostgreSQL
- [ ] Create `ooa_conversations` table (already coded, needs deployment)
- [ ] Add session cleanup job (delete after 7 days idle)
- [ ] Add session export feature
- [ ] Test session continuity across server restarts

### Error Handling & Resilience
- [ ] Retry logic for transient Odoo failures (3 attempts, exponential backoff)
- [ ] Circuit breaker for Odoo connection failures
- [ ] Graceful degradation when Anthropic API is down
- [ ] Better user-facing error messages
- [ ] Error tracking via Sentry

### Monitoring & Observability
- [ ] Set up Sentry for error tracking
- [ ] Add Prometheus metrics endpoint
- [ ] Track: response latency, token usage, error rate, cache hit rate
- [ ] Set up Grafana dashboards
- [ ] Configure alerts (PagerDuty / email)
- [ ] Log aggregation (Loki or CloudWatch)

### Rate Limiting
- [ ] Add `slowapi` rate limiter to FastAPI
- [ ] Limit per session: 60 requests/hour
- [ ] Limit per IP: 200 requests/hour
- [ ] Track Anthropic token usage per session
- [ ] Set monthly budget caps

### Performance Tuning
- [ ] Database connection pooling (pgbouncer or built-in)
- [ ] HTTP/2 support via Hypercorn instead of Uvicorn
- [ ] Compression middleware (gzip)
- [ ] CDN for frontend static assets

---

## 🔒 Priority 3 — Security

### Authentication & Authorization
- [ ] Add OAuth2 / JWT authentication
- [ ] Implement role-based access control (RBAC)
- [ ] User-Odoo permission mapping
- [ ] Audit log for sensitive operations
- [ ] MFA for admin accounts

### Data Protection
- [ ] Encrypt `.env` secrets via HashiCorp Vault or AWS Secrets Manager
- [ ] HTTPS only — redirect HTTP
- [ ] Secure cookies (HttpOnly, SameSite)
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries everywhere)
- [ ] XSS prevention in React (already React's default)

### Compliance
- [ ] GDPR-style data deletion endpoint
- [ ] Session anonymization for analytics
- [ ] Data residency: ensure UAE data stays in region
- [ ] Audit logs retention policy (90 days)

---

## 📋 Priority 4 — CI/CD

### Continuous Integration
- [ ] GitHub Actions workflow for tests
- [ ] Run pytest on every push
- [ ] Lint with ruff
- [ ] Type check with mypy
- [ ] Frontend tests with Jest

### Continuous Deployment
- [ ] Auto-deploy main branch to staging server
- [ ] Manual deploy to production
- [ ] Blue-green deployment strategy
- [ ] Docker image tagging by commit SHA
- [ ] Rollback procedure documented

### Backup & Disaster Recovery
- [ ] Daily backup of Redis cache (low priority — can rebuild)
- [ ] Daily backup of `ooa_conversations` table
- [ ] Weekly backup of `.env` to encrypted storage
- [ ] Test restore procedure quarterly
- [ ] Document DR runbook

---

## 📋 Priority 5 — Future Architecture

### Multi-Tenancy
- [ ] Support multiple Odoo clients (not just Elrace)
- [ ] Tenant isolation in database
- [ ] Per-tenant configuration
- [ ] Per-tenant API keys

### Microservices Split (Long Term)
- [ ] Extract `voice_engine` to separate service
- [ ] Extract `accounting_connector` to separate service
- [ ] gRPC between services
- [ ] Service mesh (Istio or Linkerd)

### Odoo 18 Migration
- [ ] Build `adapters/v18/connector.py` using REST API
- [ ] Migrate AI gateway methods to Odoo 18 module format
- [ ] Test compatibility with Odoo 18 ORM changes
- [ ] Maintain v14 and v18 adapters in parallel

### Caching Strategy v2
- [ ] CDN for static reports
- [ ] Edge caching for common queries
- [ ] Push-based cache invalidation when Odoo data changes
- [ ] Materialized views in PostgreSQL replica for heavy reports

### Cost Optimization
- [ ] Anthropic prompt caching (cache_creation tokens)
- [ ] Cache common system prompt (saves 30% tokens)
- [ ] Use Claude Haiku for simple queries
- [ ] Use Claude Sonnet only for complex tool use
- [ ] Token usage analytics dashboard

---

## 🎯 INFRASTRUCTURE METRICS TO TRACK

```
Production Health:
- Odoo primary CPU % (target: < 50% with AI active)
- Replica lag (target: < 2s)
- API response time p50, p95, p99
- Error rate (target: < 0.1%)
- Cache hit rate (target: > 60%)

Cost Metrics:
- Anthropic API tokens per day
- OpenAI Whisper minutes per day
- ElevenLabs characters per day
- Server costs (VPS + DB + Redis)
- Cost per query

Security Metrics:
- Failed authentication attempts
- Rate limit hits
- Suspicious query patterns
```

---

## 📝 ARCHITECTURE DECISION RECORDS (ADRs)

### ADR-001: Use Claude as Agent, Not Pipeline
**Decision:** Replaced LangGraph state machine with Claude native tool use.
**Reason:** Pipelines are rigid. Claude handles natural language in any way better than hardcoded routing.
**Status:** Adopted

### ADR-002: Custom AI Gateway Methods in Odoo
**Decision:** Write custom `get_ai_*` methods on `project.financial.service` instead of calling Odoo wizards directly.
**Reason:** TransientModel wizards return ORM recordsets that fail XML-RPC serialization.
**Status:** Adopted

### ADR-003: Read Replica for AI Queries
**Decision:** AI queries go to PostgreSQL read replica, not production Odoo.
**Reason:** AI queries cause 700% CPU spikes that affect real users.
**Status:** In Progress

### ADR-004: SSE Streaming Over WebSockets
**Decision:** Use Server-Sent Events instead of WebSockets for response streaming.
**Reason:** Simpler, unidirectional fits our use case, better browser support.
**Status:** Adopted

### ADR-005: Docker for All Deployments
**Decision:** Containerize everything via Docker.
**Reason:** Consistent environments, easy rollback, simple scaling.
**Status:** Adopted

---

## 🚨 RUNBOOK SHORTCUTS

### Service Down
```bash
# Check if container running
docker ps | grep ooa

# Check logs
docker logs ooa --tail 100

# Restart
docker restart ooa
```

### High CPU on Odoo
```bash
# Check if AI is hitting Odoo (should be replica only)
# Check PG_HOST in OOA .env points to replica
# Check Redis cache hit rate
docker exec redis redis-cli INFO stats
```

### Replica Lag
```bash
# On primary
SELECT client_addr, state, sync_state, replay_lag
FROM pg_stat_replication;

# On replica
SELECT now() - pg_last_xact_replay_timestamp() AS lag;
```

### Cache Issues
```bash
# Flush all cache
curl -X DELETE http://localhost:8000/cache

# Check Redis memory
docker exec redis redis-cli INFO memory
```

---

## 📝 NOTES FOR DEVOPS

When making infrastructure changes:

1. **Test in dev first** — never deploy untested to production
2. **Document the change** — add ADR if architectural
3. **Update environment variables** — keep `.env.example` current
4. **Monitor after deployment** — check metrics for 30 minutes minimum
5. **Have rollback ready** — Docker tags make this easy
6. **Notify team** — especially before maintenance windows
