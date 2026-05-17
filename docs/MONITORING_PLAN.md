# MONITORING & OBSERVABILITY PLAN

> **Goal:** Build comprehensive observability into the admin panel — every API call, every token spent, every container metric, every Odoo response time visible in beautiful dashboards with real-time alerts.

> **Strategic principle:** You cannot improve what you cannot measure. Every component must emit metrics. Every dashboard must answer a specific business question.

---

# PART I — OBSERVABILITY ARCHITECTURE

## 1. The Three Pillars

```
┌──────────────────────────────────────────────────────────────┐
│                    METRICS                                    │
│  Quantitative measurements over time                          │
│  - API response times, request counts                         │
│  - Token usage, costs                                         │
│  - CPU, memory, network                                       │
│  - Cache hit rates                                            │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│                    LOGS                                       │
│  Discrete events with context                                 │
│  - Structured JSON logs                                       │
│  - Errors with stack traces                                   │
│  - Audit trail                                                │
│  - Query history                                              │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│                    TRACES                                     │
│  End-to-end request flows                                     │
│  - User query → Claude → Tool → Odoo → Response               │
│  - Identify bottlenecks                                       │
│  - Distributed tracing                                        │
└──────────────────────────────────────────────────────────────┘
```

## 2. Tech Stack

```
Metrics:        Prometheus + Grafana
Logs:           Loki (Grafana stack) OR Elasticsearch
Traces:         OpenTelemetry + Tempo
Container:      cAdvisor + Node Exporter
DB:             pg_stat_statements + Postgres Exporter
Alerts:         Alertmanager + Email/Slack
API costs:      Custom tracker in PostgreSQL
Frontend:       Custom dashboards in React Admin Panel
```

---

# PART II — WHAT TO MONITOR

## 3. The Five Critical Categories

### Category 1: AI Operations
```
✦ Total queries per minute/hour/day
✦ Average response time (Claude API)
✦ Token consumption (input + output)
✦ Cost per query (running total)
✦ Tool invocations (which tools, how often)
✦ Failed queries and reasons
✦ Streaming connection counts
✦ Conversation length distribution
✦ Top users by query volume
✦ Top users by cost
```

### Category 2: API Provider Health
```
ANTHROPIC (Claude):
  ✦ Account balance / credits remaining
  ✦ Daily/monthly token usage
  ✦ Rate limit status
  ✦ API response time
  ✦ Error rate by error type
  ✦ Cost burn rate (USD/day)

OPENAI (Whisper STT):
  ✦ Monthly minutes used
  ✦ Cost per audio minute
  ✦ Average transcription latency
  ✦ Failed transcriptions

ELEVENLABS (TTS):
  ✦ Character credits remaining
  ✦ Voice generation time
  ✦ Failed generations
  ✦ Per-language usage breakdown
```

### Category 3: Infrastructure
```
CONTAINERS:
  ✦ CPU usage per container
  ✦ Memory usage per container
  ✦ Disk I/O
  ✦ Network I/O
  ✦ Container restarts
  ✦ Health check status
  ✦ Uptime

POSTGRESQL:
  ✦ Active connections
  ✦ Query throughput
  ✦ Slow queries (>1s)
  ✦ Index hit rate
  ✦ Cache hit rate
  ✦ Table sizes
  ✦ Lock waits
  ✦ Replication lag (when replica live)
  ✦ Disk usage

REDIS:
  ✦ Memory usage
  ✦ Hit rate / miss rate
  ✦ Connected clients
  ✦ Operations per second
  ✦ Evictions

NETWORK:
  ✦ Bandwidth in/out
  ✦ Active connections
  ✦ Latency to Odoo
  ✦ Latency to Anthropic
  ✦ DNS resolution time
```

### Category 4: Odoo Integration
```
✦ XML-RPC call latency (p50, p95, p99)
✦ Calls per method (top tools used)
✦ Failed XML-RPC calls
✦ Authentication retries
✦ Direct SQL query latency (when replica live)
✦ Odoo server CPU impact (cross-correlated)
✦ Method-level timing:
    - get_ai_financial_report: avg 1.2s
    - get_ai_general_ledger: avg 0.8s
    - search_odoo: avg 0.3s
```

### Category 5: User Behavior
```
✦ Daily active users
✦ Sessions per day
✦ Average session duration
✦ Bounce rate (single query sessions)
✦ Voice vs text usage ratio
✦ PDF generation count
✦ Suggestion click-through rate
✦ Error rate by user
✦ Geographic distribution (UAE regions)
✦ Department-wise usage
```

---

# PART III — METRICS COLLECTION

## 4. Backend Instrumentation

### 4.1 Add Prometheus Metrics

```python
# gateway/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from prometheus_client.core import CollectorRegistry

# Custom registry
registry = CollectorRegistry()

# ─── API Request Metrics ────────────────────────────────────────
api_requests_total = Counter(
    'ooa_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status_code'],
    registry=registry,
)

api_request_duration = Histogram(
    'ooa_api_request_duration_seconds',
    'API request duration',
    ['endpoint', 'method'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry,
)

# ─── AI Operations ──────────────────────────────────────────────
ai_queries_total = Counter(
    'ooa_ai_queries_total',
    'Total AI queries',
    ['user_id', 'language', 'status'],
    registry=registry,
)

ai_tokens_consumed = Counter(
    'ooa_ai_tokens_consumed_total',
    'Total tokens consumed',
    ['type', 'model'],  # type: 'input' or 'output'
    registry=registry,
)

ai_cost_cents = Counter(
    'ooa_ai_cost_cents_total',
    'AI cost in cents',
    ['provider', 'service'],  # anthropic, openai, elevenlabs
    registry=registry,
)

ai_response_time = Histogram(
    'ooa_ai_response_time_seconds',
    'AI response time',
    ['model', 'has_tool_use'],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0],
    registry=registry,
)

# ─── Tool Execution ─────────────────────────────────────────────
tool_executions = Counter(
    'ooa_tool_executions_total',
    'Tool execution count',
    ['tool_name', 'status'],
    registry=registry,
)

tool_duration = Histogram(
    'ooa_tool_duration_seconds',
    'Tool execution duration',
    ['tool_name'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=registry,
)

# ─── Odoo Integration ───────────────────────────────────────────
odoo_calls = Counter(
    'ooa_odoo_calls_total',
    'Odoo XML-RPC calls',
    ['method', 'status'],
    registry=registry,
)

odoo_call_duration = Histogram(
    'ooa_odoo_call_duration_seconds',
    'Odoo call duration',
    ['method'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry,
)

# ─── Cache ──────────────────────────────────────────────────────
cache_operations = Counter(
    'ooa_cache_operations_total',
    'Cache operations',
    ['operation', 'result'],  # operation: get/set, result: hit/miss
    registry=registry,
)

# ─── Auth & Sessions ────────────────────────────────────────────
login_attempts = Counter(
    'ooa_login_attempts_total',
    'Login attempts',
    ['status', 'reason'],
    registry=registry,
)

active_sessions = Gauge(
    'ooa_active_sessions',
    'Currently active sessions',
    registry=registry,
)

# ─── User Activity ──────────────────────────────────────────────
active_users = Gauge(
    'ooa_active_users',
    'Currently active users',
    ['time_window'],  # 1m, 5m, 1h
    registry=registry,
)

# ─── External API Health ────────────────────────────────────────
api_credits_remaining = Gauge(
    'ooa_api_credits_remaining',
    'API credits/balance remaining',
    ['provider'],
    registry=registry,
)

api_provider_up = Gauge(
    'ooa_api_provider_up',
    'External API provider status (1=up, 0=down)',
    ['provider'],
    registry=registry,
)


# Expose metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint."""
    return Response(content=generate_latest(registry), media_type="text/plain")
```

### 4.2 Instrument All Operations

```python
# Middleware for all API calls
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    api_requests_total.labels(
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
    ).inc()

    api_request_duration.labels(
        endpoint=request.url.path,
        method=request.method,
    ).observe(duration)

    return response


# Instrument tool execution
def execute_tool(tool_name, tool_input, adapter):
    start = time.time()
    try:
        result = _execute_tool_inner(tool_name, tool_input, adapter)
        tool_executions.labels(tool_name=tool_name, status='success').inc()
        return result
    except Exception as exc:
        tool_executions.labels(tool_name=tool_name, status='error').inc()
        raise
    finally:
        tool_duration.labels(tool_name=tool_name).observe(time.time() - start)


# Instrument Claude API calls
async def call_claude(messages, ...):
    start = time.time()
    response = await client.messages.create(...)

    ai_tokens_consumed.labels(type='input', model=MODEL).inc(response.usage.input_tokens)
    ai_tokens_consumed.labels(type='output', model=MODEL).inc(response.usage.output_tokens)

    # Cost calculation (current Claude pricing)
    cost_cents = (
        response.usage.input_tokens * 0.0003 +   # $3/M input
        response.usage.output_tokens * 0.0015    # $15/M output
    )
    ai_cost_cents.labels(provider='anthropic', service='claude').inc(cost_cents)

    ai_response_time.labels(
        model=MODEL,
        has_tool_use=str(response.stop_reason == "tool_use"),
    ).observe(time.time() - start)

    return response
```

### 4.3 API Credit Tracking

```python
# Periodic job to check API balances
async def check_api_credits():
    """Run every 15 minutes."""

    # Anthropic - check via API
    try:
        resp = await httpx.get(
            "https://api.anthropic.com/v1/organizations/usage",
            headers={"x-api-key": ANTHROPIC_KEY},
        )
        data = resp.json()
        api_credits_remaining.labels(provider='anthropic').set(
            data.get('credit_balance_usd', 0) * 100  # cents
        )
        api_provider_up.labels(provider='anthropic').set(1)
    except Exception:
        api_provider_up.labels(provider='anthropic').set(0)

    # OpenAI - check via usage endpoint
    try:
        resp = await httpx.get(
            "https://api.openai.com/v1/usage",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        )
        # Process and store
    except Exception:
        api_provider_up.labels(provider='openai').set(0)

    # ElevenLabs - check character quota
    try:
        resp = await httpx.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": ELEVENLABS_KEY},
        )
        data = resp.json()
        remaining = data["character_limit"] - data["character_count"]
        api_credits_remaining.labels(provider='elevenlabs').set(remaining)
    except Exception:
        api_provider_up.labels(provider='elevenlabs').set(0)


# Schedule via APScheduler or similar
@app.on_event("startup")
async def schedule_credit_checks():
    scheduler.add_job(check_api_credits, 'interval', minutes=15)
    scheduler.start()
```

---

# PART IV — INFRASTRUCTURE MONITORING

## 5. Docker Container Monitoring

### 5.1 docker-compose.yml — Full Stack

```yaml
version: '3.8'

services:
  # ─── Application ───────────────────────────────
  ooa:
    image: ooa:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:devpass@postgres:5432/ooa
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    labels:
      - "com.docker.metrics.scrape=true"

  # ─── Database ──────────────────────────────────
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=devpass
      - POSTGRES_DB=ooa
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./monitoring/postgres-init.sh:/docker-entrypoint-initdb.d/init.sh
    ports:
      - "5432:5432"
    command: postgres -c shared_preload_libraries=pg_stat_statements
                      -c pg_stat_statements.track=all

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      - DATA_SOURCE_NAME=postgresql://postgres:devpass@postgres:5432/ooa?sslmode=disable
    ports:
      - "9187:9187"

  # ─── Cache ─────────────────────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"

  redis_exporter:
    image: oliver006/redis_exporter:latest
    environment:
      - REDIS_ADDR=redis:6379
    ports:
      - "9121:9121"

  # ─── Container Metrics ─────────────────────────
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro

  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--path.rootfs=/rootfs'

  # ─── Metrics Storage ───────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'

  # ─── Log Aggregation ───────────────────────────
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/config.yml
      - loki_data:/loki

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./monitoring/promtail-config.yml:/etc/promtail/config.yml

  # ─── Visualization ─────────────────────────────
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3030:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_AUTH_ANONYMOUS_ENABLED=false

  # ─── Alerting ──────────────────────────────────
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml

volumes:
  pgdata:
  prometheus_data:
  loki_data:
  grafana_data:
```

### 5.2 Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ooa-app'
    static_configs:
      - targets: ['ooa:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres_exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis_exporter:9121']

  - job_name: 'containers'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'node'
    static_configs:
      - targets: ['node_exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - '/etc/prometheus/rules/*.yml'
```

---

# PART V — STRUCTURED LOGGING

## 6. Application Logs

### 6.1 Structured JSON Logging

```python
# gateway/logging_config.py
import logging
import json
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['service'] = 'ooa'
        log_record['logger'] = record.name

        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


def setup_logging():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# Usage
logger = logging.getLogger(__name__)
logger.info(
    "AI query completed",
    extra={
        "user_id": user.id,
        "request_id": request_id,
        "query": user_message[:100],
        "duration_ms": duration_ms,
        "tokens_used": tokens,
        "cost_cents": cost,
        "tools_called": tool_names,
    }
)
```

### 6.2 Log Categories

```python
# Different log streams for different purposes
LOG_CATEGORIES = {
    "audit":       "Security/compliance events",
    "performance": "Slow queries, timeouts",
    "errors":      "Application errors",
    "ai":          "AI queries and responses",
    "api":         "External API calls",
    "infra":       "Container/database events",
    "user":        "User actions",
    "system":      "System startup/shutdown",
}

# Each gets routed to different log file / Loki label
```

---

# PART VI — DISTRIBUTED TRACING

## 7. End-to-End Request Tracing

```python
# Use OpenTelemetry to trace requests across services
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://tempo:4317"))
)
tracer = trace.get_tracer(__name__)


# Trace example
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    with tracer.start_as_current_span("chat_stream") as span:
        span.set_attribute("user_id", user.id)
        span.set_attribute("query", request.message[:100])

        with tracer.start_as_current_span("claude_call"):
            response = await call_claude(...)

        with tracer.start_as_current_span("tool_execution"):
            for tool_call in tool_calls:
                with tracer.start_as_current_span(f"tool.{tool_call.name}"):
                    result = await execute_tool(...)

                    with tracer.start_as_current_span("odoo_call"):
                        odoo_result = await adapter.call(...)

        # Trace shows complete flow:
        # chat_stream (5.2s)
        #   └─ claude_call (1.8s)
        #   └─ tool_execution (3.1s)
        #       └─ tool.get_financial_report (3.0s)
        #           └─ odoo_call (2.9s)
        #   └─ claude_call_final (0.3s)
```

---

# PART VII — ADMIN PANEL DASHBOARDS

## 8. Dashboard Architecture

The admin panel includes 8 specialized dashboards:

```
1. Overview Dashboard         — Big picture, all key metrics
2. AI Operations Dashboard    — Queries, tokens, costs
3. API Health Dashboard       — Provider statuses, credits
4. Infrastructure Dashboard   — Containers, DB, cache
5. Odoo Integration Dashboard — XML-RPC performance
6. User Activity Dashboard    — Behavior analytics
7. Logs Explorer              — Search/filter logs
8. Alerts Dashboard           — Active alerts, history
```

### 8.1 Overview Dashboard (Wireframe)

```
┌────────────────────────────────────────────────────────────────────┐
│  SYSTEM OVERVIEW                          Last 24h ▼  [Refresh]   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │  Active  │ │ Queries  │ │  Cost    │ │   API    │ │   DB    │ │
│  │  Users   │ │  Today   │ │  Today   │ │  Health  │ │  Conns  │ │
│  │   42     │ │  2,341   │ │ $12.40   │ │ ●●●●●    │ │  18/100 │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │
│                                                                    │
│  Query Volume (Last 24h)              Response Time (p95)         │
│  ┌────────────────────────────┐      ┌────────────────────────┐  │
│  │     ▁▂▃▅▇▆▅▄▃▂▁           │      │ ───╱╲──╱─╲──╱╲──       │  │
│  │                            │      │                        │  │
│  │  0   6   12   18   24      │      │ Current: 2.3s          │  │
│  └────────────────────────────┘      └────────────────────────┘  │
│                                                                    │
│  Top Users (by query count)         Top Tools (called)            │
│  ┌────────────────────────────┐      ┌────────────────────────┐  │
│  │ Ahmed Al-Maktoum    143    │      │ get_pandl       423    │  │
│  │ Sara Mohammed       89     │      │ query_accounting 312   │  │
│  │ M Jawad             67     │      │ search_odoo      198   │  │
│  │ Ali Hassan          54     │      │ generate_pdf     67    │  │
│  └────────────────────────────┘      └────────────────────────┘  │
│                                                                    │
│  Active Alerts                                                    │
│  ⚠ Odoo XML-RPC slow (avg 3.2s — threshold 2s)                  │
│  ⚠ ElevenLabs credits low (12% remaining)                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 8.2 AI Operations Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  AI OPERATIONS                              [Live] [Last 24h ▼]   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────┐ ┌─────────────────────────────────┐  │
│  │ Tokens Today            │ │ Cost Breakdown (USD)            │  │
│  │  Input:   1,234,567     │ │  Anthropic Claude:   $10.20    │  │
│  │  Output:    345,678     │ │  OpenAI Whisper:     $1.40     │  │
│  │  Total:   1,580,245     │ │  ElevenLabs TTS:     $0.80     │  │
│  │                         │ │  ────────────────────           │  │
│  │  Monthly avg: 47M       │ │  TOTAL:              $12.40    │  │
│  │  Projection: $384/mo    │ │                                 │  │
│  └─────────────────────────┘ └─────────────────────────────────┘  │
│                                                                    │
│  Query Latency Distribution                                       │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  p50: 1.2s ████                                              ││
│  │  p75: 2.4s ██████████                                        ││
│  │  p95: 4.8s ████████████████                                  ││
│  │  p99: 8.2s ████████████████████████                          ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  Tool Performance                                                 │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Tool                    Count  Avg Time  P95     Errors    ││
│  │  query_accounting        312   850ms     2.1s    2          ││
│  │  search_odoo             198   230ms     480ms   0          ││
│  │  get_pandl               423   1.2s      2.8s    5          ││
│  │  generate_pdf_report     67    3.4s      6.2s    1          ││
│  │  group_and_aggregate     145   980ms     2.4s    8 ⚠         ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  Recent Failed Queries (last 10)                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  10:32 ahmed.k - "complex query..." - timeout                ││
│  │  10:28 sara.m  - "show me X..."     - tool error             ││
│  │  ...                                                          ││
│  └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

### 8.3 API Health Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  EXTERNAL API HEALTH                                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ANTHROPIC (Claude)                              Status: ● UP     │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ Account Balance:    $487.32                                   ││
│  │ Burn Rate:          $12.40/day                                ││
│  │ Days Remaining:     ~39 days at current rate                  ││
│  │ Today's Tokens:     1,580,245                                 ││
│  │ Today's Cost:       $10.20                                    ││
│  │ Rate Limit:         200/min (using 23 avg)                    ││
│  │ Response Time:      avg 1.8s, p95 4.2s                        ││
│  │ Error Rate:         0.3% (3 failures / 1024 calls)            ││
│  │                                                                ││
│  │ [View detailed logs] [Refresh credits]                        ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  OPENAI (Whisper)                                Status: ● UP     │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ Monthly Usage:      234 / 500 minutes                         ││
│  │ Today's Minutes:    8.3                                       ││
│  │ Cost MTD:           $1.40                                     ││
│  │ Avg Transcription:  1.2s                                      ││
│  │ Failed:             0 today                                   ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  ELEVENLABS (TTS)                                Status: ⚠ LOW    │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │ Character Credits:  12,450 / 100,000 remaining (12%)          ││
│  │ Today's Usage:      8,234 characters                          ││
│  │ Voice Generation:   avg 1.8s                                  ││
│  │ ⚠ ACTION NEEDED:   Upgrade plan or wait for monthly reset    ││
│  │                                                                ││
│  │ [Upgrade subscription] [View usage history]                   ││
│  └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

### 8.4 Infrastructure Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE                                  [Refresh: 5s]    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  CONTAINER METRICS                                                │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Container       CPU%     Mem      Disk I/O   Net I/O       ││
│  │  ──────────────────────────────────────────────────────────  ││
│  │  ooa             15%      340 MB   12 MB/s    8 MB/s         ││
│  │  postgres        8%       512 MB   45 MB/s    2 MB/s         ││
│  │  redis           1%       45 MB    1 MB/s     0.5 MB/s       ││
│  │  prometheus      3%       180 MB   8 MB/s     1 MB/s         ││
│  │  grafana         2%       95 MB    2 MB/s     0.3 MB/s       ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  POSTGRESQL                                                       │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Active Connections:     18 / 100                             ││
│  │  Cache Hit Rate:         97.3% (excellent)                    ││
│  │  Index Hit Rate:         99.1%                                ││
│  │  Queries/sec:            142                                  ││
│  │  Slow Queries (>1s):     3 in last hour                       ││
│  │  Database Size:          1.2 GB                               ││
│  │  Largest Tables:         messages (840MB), audit_logs (320MB)││
│  │  Replication Lag:        N/A (replica not yet live)          ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  REDIS                                                            │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Memory Used:            45 MB / 512 MB (8.8%)                ││
│  │  Hit Rate:               78.4%                                ││
│  │  Connected Clients:      12                                   ││
│  │  Operations/sec:         234                                  ││
│  │  Evictions:              0                                    ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  NETWORK                                                          │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Bandwidth In:           24 Mbps                              ││
│  │  Bandwidth Out:          18 Mbps                              ││
│  │  Latency to Odoo:        67ms avg, 124ms p95                  ││
│  │  Latency to Anthropic:   140ms avg, 220ms p95                 ││
│  │  Active TCP Conns:       47                                   ││
│  └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

### 8.5 Odoo Integration Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  ODOO INTEGRATION HEALTH                                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  XML-RPC METHOD PERFORMANCE                                       │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Method                          Calls  Avg    P95    Errs  ││
│  │  ────────────────────────────────────────────────────────────││
│  │  search_read                     234    180ms  450ms  0     ││
│  │  get_ai_financial_report         123    1.2s   2.8s   2  ⚠  ││
│  │  get_ai_general_ledger           67     1.5s   3.2s   1     ││
│  │  get_project_expense_dashboard   45     2.1s   4.5s   0  ⚠  ││
│  │  authenticate                    8      230ms  450ms  0     ││
│  │  ai_group_and_aggregate          189    980ms  2.4s   8     ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  ODOO SERVER IMPACT (cross-correlation)                           │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  When AI is active, Odoo CPU spikes correlate at 78%         ││
│  │  Avg Odoo CPU during AI query: 340%                          ││
│  │  ⚠ ACTION: Move to read replica (Phase 1 in TASKS_ARCHITECTURE)││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  FAILED CALLS (last 10)                                           │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  10:42 get_ai_financial_report   timeout    period: Q1       ││
│  │  10:35 get_ai_general_ledger     timeout    period: Year     ││
│  │  10:28 group_and_aggregate       field err  field: type      ││
│  │  ...                                                          ││
│  │  [Click any to see full request/response]                    ││
│  └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

### 8.6 User Activity Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  USER ACTIVITY                                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ENGAGEMENT METRICS                                               │
│  ┌─────────────────────┐ ┌─────────────────────┐                 │
│  │ Daily Active Users  │ │ Avg Session Length  │                 │
│  │       42            │ │     8m 24s          │                 │
│  │ ↗ +18% vs last week│ │ ↘ -2m vs last week │                 │
│  └─────────────────────┘ └─────────────────────┘                 │
│                                                                    │
│  ACTIVITY BY DEPARTMENT                                           │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Finance      ████████████ 423 queries (35%)                 ││
│  │  Project Mgt  █████████ 312 queries (26%)                    ││
│  │  Sales        ████ 189 queries (16%)                         ││
│  │  Procurement  ███ 145 queries (12%)                          ││
│  │  HR           ██ 89 queries (7%)                             ││
│  │  IT           █ 45 queries (4%)                              ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  FEATURE USAGE                                                    │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  Text queries:      87%                                       ││
│  │  Voice queries:     13%                                       ││
│  │  PDF generated:     67 today                                  ││
│  │  Drill-downs:       234 today                                 ││
│  │  Suggestions clicked: 56%                                     ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  HOURLY ACTIVITY (today)                                          │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                       ▁▂▃▅▇▆▅▄▃                              ││
│  │              ▂▃▅▇████████████▆▅▃                              ││
│  │    ▁▂▃▅▆▇████████████████████████▇▅▃                          ││
│  │  00 02 04 06 08 10 12 14 16 18 20 22                         ││
│  │                                                                ││
│  │  Peak: 10am - 2pm (UAE business hours)                       ││
│  └──────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
```

### 8.7 Logs Explorer

```
┌────────────────────────────────────────────────────────────────────┐
│  LOGS EXPLORER                                                    │
├────────────────────────────────────────────────────────────────────┤
│  Service: [All ▼]  Level: [All ▼]  Time: [Last 1h ▼]             │
│  Search: [error timeout odoo___________]  [Apply Filter]          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  10:42:35.123  ERROR  ooa.tools  Odoo timeout on get_ai_financial │
│                            user_id=42 duration_ms=30000           │
│                            [View trace] [Similar errors]          │
│                                                                    │
│  10:42:34.891  WARN   ooa.cache  Cache miss for query_accounting  │
│                            key=abc123... ttl=300                  │
│                                                                    │
│  10:42:34.567  INFO   ooa.auth   User logged in                   │
│                            user_id=42 ip=192.168.1.45             │
│                                                                    │
│  10:42:34.234  INFO   ooa.query  AI query completed               │
│                            user_id=42 duration_ms=1247 tokens=523 │
│                                                                    │
│  ...                                                              │
│                                                                    │
│  [Load older]                              Showing 50 of 12,453   │
└────────────────────────────────────────────────────────────────────┘

Features:
✦ Full-text search across all logs
✦ Filter by service, level, user, time
✦ Click any log → see full JSON + related context
✦ Save common filters as bookmarks
✦ Export to CSV
✦ Click error → see trace + similar errors
```

### 8.8 Alerts Dashboard

```
┌────────────────────────────────────────────────────────────────────┐
│  ALERTS & INCIDENTS                                               │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ACTIVE ALERTS (3)                                                │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  ⚠  HIGH    Odoo response time elevated                      ││
│  │            avg 3.2s (threshold 2s) for last 15 min            ││
│  │            Started: 10:30 AM    [Acknowledge] [Silence 1h]    ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │  ⚠  MEDIUM  ElevenLabs credits low                           ││
│  │            12% remaining (threshold: 20%)                     ││
│  │            Started: Yesterday   [Upgrade plan] [Silence]      ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │  ⚠  LOW     Slow queries in PostgreSQL                       ││
│  │            5 queries exceeded 1s in last hour                 ││
│  │            Started: 10:15 AM    [View queries] [Acknowledge] ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  RECENT INCIDENTS (Last 7 days)                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  May 12, 2:34 PM   Database connection pool exhausted        ││
│  │                    Duration: 12 min                           ││
│  │                    Resolution: Increased pool size            ││
│  │                                                                ││
│  │  May 10, 9:15 AM   Anthropic API outage                      ││
│  │                    Duration: 3 hours                          ││
│  │                    Status: Resolved (provider issue)         ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                    │
│  ALERT RULES                                                      │
│  [Configure] - Manage all alert thresholds                       │
└────────────────────────────────────────────────────────────────────┘
```

---

# PART VIII — ALERTING RULES

## 9. Critical Alerts

```yaml
# monitoring/alert-rules.yml
groups:
  - name: ooa_critical
    interval: 30s
    rules:

      # ─── Service Health ─────────────────────
      - alert: ServiceDown
        expr: up{job="ooa-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OOA service is down"

      - alert: HighErrorRate
        expr: |
          rate(ooa_api_requests_total{status_code=~"5.."}[5m]) /
          rate(ooa_api_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: high
        annotations:
          summary: "Error rate >5% for 2 minutes"

      # ─── AI Provider Health ─────────────────
      - alert: AnthropicCreditsLow
        expr: ooa_api_credits_remaining{provider="anthropic"} < 5000
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "Anthropic credits below $50"

      - alert: ElevenLabsCreditsLow
        expr: ooa_api_credits_remaining{provider="elevenlabs"} < 10000
        for: 5m
        labels:
          severity: medium
        annotations:
          summary: "ElevenLabs character credits <10k"

      - alert: APIProviderDown
        expr: ooa_api_provider_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "External API provider {{ $labels.provider }} is down"

      # ─── Performance ─────────────────────────
      - alert: SlowAIResponse
        expr: |
          histogram_quantile(0.95,
            rate(ooa_ai_response_time_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: medium
        annotations:
          summary: "AI response p95 >10s"

      - alert: SlowOdooCalls
        expr: |
          histogram_quantile(0.95,
            rate(ooa_odoo_call_duration_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: medium
        annotations:
          summary: "Odoo XML-RPC p95 >3s"

      # ─── Database ────────────────────────────
      - alert: DatabaseConnectionsHigh
        expr: |
          pg_stat_database_numbackends{datname="ooa"} > 80
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "PostgreSQL connections >80% of pool"

      - alert: DatabaseSlowQueries
        expr: |
          rate(pg_stat_statements_total_time_seconds[5m]) > 60
        labels:
          severity: medium

      # ─── Infrastructure ──────────────────────
      - alert: HighMemoryUsage
        expr: |
          (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) < 0.1
        for: 5m
        labels:
          severity: high

      - alert: HighCPUUsage
        expr: |
          (1 - rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100 > 80
        for: 10m
        labels:
          severity: medium

      - alert: ContainerRestarted
        expr: changes(container_start_time_seconds[5m]) > 0
        labels:
          severity: high
        annotations:
          summary: "Container {{ $labels.name }} restarted"

      # ─── Security ────────────────────────────
      - alert: HighLoginFailureRate
        expr: |
          rate(ooa_login_attempts_total{status="failure"}[5m]) > 1
        for: 5m
        labels:
          severity: medium
        annotations:
          summary: ">5 failed logins in 5 minutes"

      - alert: SuspiciousActivity
        expr: |
          rate(ooa_login_attempts_total{status="failure"}[5m]) > 10
        labels:
          severity: critical
        annotations:
          summary: "Possible brute force attack"

      # ─── Cost ────────────────────────────────
      - alert: DailyCostExceedsThreshold
        expr: ooa_ai_cost_cents_total > 5000  # $50/day
        labels:
          severity: high
        annotations:
          summary: "Daily AI cost >$50"
```

## 10. Notification Channels

```yaml
# monitoring/alertmanager.yml
route:
  group_by: ['severity', 'alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true
    - match:
        severity: high
      receiver: 'high-alerts'

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@elrace.com'

  - name: 'critical-alerts'
    email_configs:
      - to: 'cto@elrace.com,m.jawad@elrace.com'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#ooa-alerts-critical'
    webhook_configs:
      - url: 'https://api.pagerduty.com/...'  # PagerDuty

  - name: 'high-alerts'
    email_configs:
      - to: 'devops@elrace.com'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#ooa-alerts'
```

---

# PART IX — IMPLEMENTATION PHASES

## 11. Build Order (6 Weeks)

### Phase 1 — Metrics Foundation (Week 1)
```
[ ] Add Prometheus metrics to gateway/main.py
[ ] Instrument all API endpoints
[ ] Instrument all tool executions
[ ] Instrument Claude API calls
[ ] Add /metrics endpoint
[ ] Test scraping locally
```

### Phase 2 — Infrastructure Stack (Week 2)
```
[ ] Update docker-compose.yml with monitoring services
[ ] Configure Prometheus
[ ] Set up Grafana
[ ] Add Postgres exporter
[ ] Add Redis exporter
[ ] Add cAdvisor and node-exporter
[ ] Verify metrics flowing
```

### Phase 3 — Structured Logging (Week 3)
```
[ ] Add JSON formatter to logging
[ ] Set up Loki
[ ] Configure Promtail
[ ] Tag logs with context (user_id, request_id)
[ ] Test log aggregation
```

### Phase 4 — API Credit Tracking (Week 4)
```
[ ] Build credit checker for Anthropic
[ ] Build credit checker for OpenAI
[ ] Build credit checker for ElevenLabs
[ ] Schedule periodic checks
[ ] Add to metrics
[ ] Test alerts on low balance
```

### Phase 5 — Admin Panel Dashboards (Week 5)
```
[ ] Build Overview dashboard
[ ] Build AI Operations dashboard
[ ] Build API Health dashboard
[ ] Build Infrastructure dashboard
[ ] Build Odoo Integration dashboard
[ ] Build User Activity dashboard
[ ] Build Logs Explorer
[ ] Build Alerts dashboard
```

### Phase 6 — Alerts & Polish (Week 6)
```
[ ] Configure all alert rules
[ ] Set up Alertmanager
[ ] Configure Slack/email notifications
[ ] Test all alerts firing correctly
[ ] Create runbooks for common issues
[ ] Document monitoring access for team
```

---

# PART X — API ENDPOINTS

## 12. Monitoring API

```
GET  /admin/metrics/overview              System overview metrics
GET  /admin/metrics/ai                    AI operations stats
GET  /admin/metrics/api-health            External API status
GET  /admin/metrics/infrastructure        Container/DB/cache metrics
GET  /admin/metrics/odoo                  Odoo integration health
GET  /admin/metrics/users                 User activity
GET  /admin/metrics/costs                 Cost breakdown by service

GET  /admin/logs?service=&level=&query=&since=&until=
                                          Search logs
GET  /admin/logs/:id                      Single log detail
GET  /admin/logs/export                   Export logs to CSV

GET  /admin/traces?request_id=            Distributed trace view

GET  /admin/alerts                        Active alerts
POST /admin/alerts/:id/acknowledge        Ack alert
POST /admin/alerts/:id/silence            Silence for duration
GET  /admin/alerts/history                Past incidents

GET  /admin/health                        Health check (all components)
```

---

# PART XI — RUNBOOKS

## 13. Common Issues Playbook

For each common alert, document the response:

### Runbook 1: Odoo Slow Response
```
Symptoms: avg response time > 2s
Diagnosis steps:
1. Check Odoo server CPU (probably high)
2. Verify query is hitting Odoo not replica
3. Check Anthropic call duration (might be Claude not Odoo)
4. Review slow queries dashboard

Resolution:
- Short term: Increase cache TTL
- Medium term: Add database indexes
- Long term: Move to read replica
```

### Runbook 2: API Credits Low
```
Symptoms: Alert fires when credits drop
Diagnosis:
1. Check current balance via dashboard
2. Check daily burn rate
3. Identify any usage spike (which user/query type)

Resolution:
- Immediate: Top up account
- Investigate spike cause
- Consider rate limiting if abuse
```

### Runbook 3: Database Connections Exhausted
```
Symptoms: Cannot connect to database
Diagnosis:
1. Check active connections
2. Look for long-running queries
3. Check for connection leaks

Resolution:
- Kill idle transactions
- Increase pool size
- Find and fix the leak in code
```

---

# PART XII — TELL CURSOR

```
"Read MONITORING_PLAN.md.

Start Phase 1: Add Prometheus metrics to the gateway.

Implementation:
1. Add prometheus-client to requirements
2. Create gateway/metrics.py with all metric definitions
3. Instrument /chat/stream endpoint
4. Instrument execute_tool function
5. Instrument Claude API calls
6. Add /metrics endpoint
7. Test with curl http://localhost:8000/metrics

Reference:
- PROJECT_CONTEXT.md for code patterns
- ADMIN_PANEL_PLAN.md for context

After Phase 1 works, move to Phase 2 (infrastructure stack with docker-compose).
"
```

---

## What This Plan Delivers

### Complete Observability
```
✦ Prometheus metrics (50+ instrumented)
✦ Structured JSON logs (Loki-ready)
✦ Distributed tracing (OpenTelemetry)
✦ Container stats (cAdvisor)
✦ Database metrics (postgres_exporter)
✦ Cache metrics (redis_exporter)
✦ System metrics (node_exporter)
```

### Admin Panel Dashboards (8 specialized)
```
✦ Overview              — Big picture
✦ AI Operations         — Queries, tokens, costs
✦ API Health            — Anthropic/OpenAI/ElevenLabs
✦ Infrastructure        — Containers, DB, Redis
✦ Odoo Integration      — XML-RPC performance
✦ User Activity         — Behavior analytics
✦ Logs Explorer         — Search interface
✦ Alerts                — Active issues, history
```

### API Credit Tracking
```
✦ Live balance for each provider
✦ Daily/monthly burn rate
✦ Days remaining at current rate
✦ Alerts when balance low
✦ Auto-refresh every 15 minutes
```

### Comprehensive Alerts
```
✦ Service down
✦ High error rate
✦ Slow responses (AI, Odoo, DB)
✦ Credit limits low
✦ Container restarts
✦ Memory/CPU high
✦ Failed login spikes
✦ Cost thresholds exceeded
```

### Runbooks
```
✦ Documented response for each alert
✦ Diagnosis steps
✦ Resolution actions
✦ Escalation paths
```

This is enterprise-grade observability. You will know exactly what is happening, where it is slow, what it costs, and when something needs attention — before users notice.
