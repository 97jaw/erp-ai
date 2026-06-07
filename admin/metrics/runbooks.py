"""Operational runbooks for Prometheus alerts (Monitoring Phase 6)."""
from __future__ import annotations

from typing import Any

RUNBOOKS: dict[str, dict[str, Any]] = {
    "OoaGatewayDown": {
        "title": "Gateway metrics endpoint down",
        "severity": "critical",
        "steps": [
            "Confirm gateway process: curl -sf http://127.0.0.1:8000/health",
            "Restart: bash scripts/start_gateway.sh (bind 0.0.0.0:8000)",
            "Check Prometheus target: ./scripts/check_gateway_scrape.sh",
            "Review logs: tail -f logs/ooa-gateway.jsonl or Grafana → Loki",
        ],
        "links": ["/admin/monitoring", "http://localhost:9090/targets"],
    },
    "OoaHighErrorRate": {
        "title": "High HTTP 5xx rate",
        "severity": "high",
        "steps": [
            "Open Admin → Monitoring → Logs; filter level ERROR",
            "Identify failing routes from ooa_api_requests_total labels",
            "Check Odoo connectivity and recent deploys",
            "Roll back or scale if load-related",
        ],
        "links": ["/admin/monitoring"],
    },
    "OoaSlowAIResponse": {
        "title": "Claude API latency high",
        "severity": "medium",
        "steps": [
            "Check Anthropic status page and API key validity",
            "Review Admin → Monitoring → AI for p95 trends",
            "Reduce concurrent heavy reports if needed",
        ],
        "links": ["/admin/monitoring"],
    },
    "OoaSlowToolExecution": {
        "title": "Odoo tool execution slow",
        "severity": "medium",
        "steps": [
            "Verify Odoo instance load and ODOO_XMLRPC_TIMEOUT",
            "Check large read_group / search_read queries in logs",
            "Test Odoo XML-RPC from scripts/verify_* if specific tool",
        ],
        "links": [],
    },
    "OoaHighLoginFailureRate": {
        "title": "Elevated failed logins",
        "severity": "medium",
        "steps": [
            "Admin → Security / audit logs for brute-force patterns",
            "Confirm AUTH_LOCKOUT_MINUTES and rate limits in .env",
            "Block offending IPs at reverse proxy if applicable",
        ],
        "links": ["/admin/security"],
    },
    "OoaPostgresExporterDown": {
        "title": "Postgres exporter unreachable",
        "severity": "high",
        "steps": [
            "Ensure admin DB is up (Homebrew 5432 or Docker 5433)",
            "Verify POSTGRES_EXPORTER_DSN in .env matches running DB",
            "docker compose -f docker-compose.monitoring.yml restart postgres_exporter",
        ],
        "links": [],
    },
    "OoaRedisExporterDown": {
        "title": "Redis exporter down",
        "severity": "warning",
        "steps": [
            "docker compose -f docker-compose.monitoring.yml ps redis redis_exporter",
            "Restart redis_exporter container",
        ],
        "links": [],
    },
    "OoaAnthropicCreditsLow": {
        "title": "Anthropic balance low",
        "severity": "high",
        "steps": [
            "Top up Anthropic billing; set ANTHROPIC_CREDIT_BUDGET_CENTS in .env",
            "Admin → Monitoring → API Health → Refresh",
            "Review Admin → Usage for spend trends",
        ],
        "links": ["/admin/usage", "/admin/monitoring"],
    },
    "OoaOpenAICreditsLow": {
        "title": "OpenAI credits low",
        "severity": "medium",
        "steps": [
            "Add prepaid credits in OpenAI dashboard",
            "Refresh API health in admin monitoring",
        ],
        "links": ["/admin/monitoring"],
    },
    "OoaElevenLabsCreditsLow": {
        "title": "ElevenLabs quota low",
        "severity": "medium",
        "steps": [
            "Upgrade ElevenLabs plan or reduce voice usage",
            "Refresh API health metrics",
        ],
        "links": ["/admin/monitoring"],
    },
    "OoaAPIProviderDown": {
        "title": "External API provider down",
        "severity": "critical",
        "steps": [
            "Admin → Monitoring → API Health; note provider error message",
            "Verify API key in .env and provider status page",
            "If key valid, wait for provider recovery; silence alert if planned maintenance",
        ],
        "links": ["/admin/monitoring"],
    },
}


def runbook_for_alert(alertname: str | None) -> dict[str, Any] | None:
    if not alertname:
        return None
    return RUNBOOKS.get(alertname)


def list_runbooks() -> list[dict[str, Any]]:
    return [{"alertname": k, **v} for k, v in RUNBOOKS.items()]
