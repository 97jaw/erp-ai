"""
Prometheus metrics for the OOA gateway (MONITORING_PLAN Phase 1).
"""
from __future__ import annotations

import re
import time
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import CollectorRegistry
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Custom registry (isolated from default process metrics unless merged later)
REGISTRY = CollectorRegistry()

from gateway.model_config import AGENT_MODEL as AGENT_MODEL_DEFAULT

# ─── API request metrics ───────────────────────────────────────────────────
api_requests_total = Counter(
    "ooa_api_requests_total",
    "Total API requests",
    ["endpoint", "method", "status_code"],
    registry=REGISTRY,
)

api_request_duration = Histogram(
    "ooa_api_request_duration_seconds",
    "API request duration in seconds",
    ["endpoint", "method"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

# ─── AI operations ───────────────────────────────────────────────────────────
ai_queries_total = Counter(
    "ooa_ai_queries_total",
    "Total AI chat queries",
    ["endpoint", "language", "status"],
    registry=REGISTRY,
)

ai_tokens_consumed = Counter(
    "ooa_ai_tokens_consumed_total",
    "Total tokens consumed",
    ["type", "model"],
    registry=REGISTRY,
)

ai_cost_cents = Counter(
    "ooa_ai_cost_cents_total",
    "Estimated AI cost in cents",
    ["provider", "service"],
    registry=REGISTRY,
)

ai_response_time = Histogram(
    "ooa_ai_response_time_seconds",
    "Claude API response time in seconds",
    ["model", "has_tool_use"],
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

ai_streaming_connections = Gauge(
    "ooa_ai_streaming_connections",
    "Active SSE chat stream connections",
    registry=REGISTRY,
)

chat_stream_duration = Histogram(
    "ooa_chat_stream_duration_seconds",
    "End-to-end /chat/stream duration in seconds",
    ["status"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)

# ─── Tool execution ──────────────────────────────────────────────────────────
tool_executions = Counter(
    "ooa_tool_executions_total",
    "Tool execution count",
    ["tool_name", "status"],
    registry=REGISTRY,
)

tool_duration = Histogram(
    "ooa_tool_duration_seconds",
    "Tool execution duration in seconds",
    ["tool_name"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

# ─── Odoo (reserved for adapter instrumentation; tool layer uses tool_* ) ───
odoo_calls = Counter(
    "ooa_odoo_calls_total",
    "Odoo XML-RPC calls",
    ["method", "status"],
    registry=REGISTRY,
)

odoo_call_duration = Histogram(
    "ooa_odoo_call_duration_seconds",
    "Odoo call duration in seconds",
    ["method"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

# ─── Cache ───────────────────────────────────────────────────────────────────
cache_operations = Counter(
    "ooa_cache_operations_total",
    "Tool result cache operations",
    ["operation", "result"],
    registry=REGISTRY,
)

# ─── Auth & sessions ─────────────────────────────────────────────────────────
login_attempts = Counter(
    "ooa_login_attempts_total",
    "Login attempts",
    ["status", "reason"],
    registry=REGISTRY,
)

active_sessions = Gauge(
    "ooa_active_sessions",
    "Currently active sessions (gauge updated by admin jobs)",
    registry=REGISTRY,
)

# ─── User activity ───────────────────────────────────────────────────────────
active_users = Gauge(
    "ooa_active_users",
    "Active users in time window",
    ["time_window"],
    registry=REGISTRY,
)

# ─── External API health (Phase 4 will populate) ───────────────────────────
api_credits_remaining = Gauge(
    "ooa_api_credits_remaining",
    "API credits or balance remaining",
    ["provider"],
    registry=REGISTRY,
)

api_provider_up = Gauge(
    "ooa_api_provider_up",
    "External API provider status (1=up, 0=down)",
    ["provider"],
    registry=REGISTRY,
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def normalize_endpoint(path: str) -> str:
    """Collapse UUID path segments to limit Prometheus label cardinality."""
    if path == "/metrics":
        return path
    return _UUID_RE.sub("{id}", path)


def metrics_payload() -> bytes:
    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


def record_claude_response(
    response: Any,
    duration_seconds: float,
    *,
    model: str = AGENT_MODEL_DEFAULT,
) -> None:
    """Record token usage, cost estimate, and latency for a Claude Messages API response."""
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0

    if input_tokens:
        ai_tokens_consumed.labels(type="input", model=model).inc(input_tokens)
    if output_tokens:
        ai_tokens_consumed.labels(type="output", model=model).inc(output_tokens)

    cost = (input_tokens * 0.0003) + (output_tokens * 0.0015)
    if cost > 0:
        ai_cost_cents.labels(provider="anthropic", service="claude").inc(cost)

    has_tool_use = str(getattr(response, "stop_reason", "")) == "tool_use"
    ai_response_time.labels(model=model, has_tool_use=str(has_tool_use).lower()).observe(
        max(duration_seconds, 0.0)
    )


def record_odoo_call(
    method: str,
    duration_seconds: float,
    *,
    status: str = "success",
) -> None:
    """Record Odoo XML-RPC call (adapter _execute)."""
    label = method[:80] if len(method) > 80 else method
    odoo_calls.labels(method=label, status=status).inc()
    odoo_call_duration.labels(method=label).observe(max(duration_seconds, 0.0))


def record_tool_execution(
    tool_name: str,
    duration_seconds: float,
    *,
    status: str,
    cached: bool = False,
) -> None:
    tool_executions.labels(tool_name=tool_name, status=status).inc()
    tool_duration.labels(tool_name=tool_name).observe(max(duration_seconds, 0.0))
    if cached:
        cache_operations.labels(operation="get", result="hit").inc()
    elif status != "denied":
        cache_operations.labels(operation="get", result="miss").inc()


def record_login_attempt(*, status: str, reason: str = "none") -> None:
    login_attempts.labels(status=status, reason=reason).inc()


def record_ai_query(
    *,
    endpoint: str,
    language: str,
    status: str,
) -> None:
    ai_queries_total.labels(
        endpoint=endpoint,
        language=language or "unknown",
        status=status,
    ).inc()


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """HTTP middleware: request counts and latency histogram per route."""

    _SKIP_PREFIXES = ("/metrics",)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._SKIP_PREFIXES):
            return await call_next(request)

        endpoint = normalize_endpoint(path)
        method = request.method
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            api_requests_total.labels(
                endpoint=endpoint,
                method=method,
                status_code=str(status_code),
            ).inc()
            api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)
