"""
OOA Phase 4 — Claude Agent Gateway (Production Architecture)
=============================================================
File    : gateway/main.py
Author  : Lead Backend Developer
Version : 3.0.0

Architecture:
    - Claude is the brain — handles ALL queries in any language
    - Odoo operations are Claude tools (function calling)
    - No pipeline, no routing, no phrase matching
    - Claude decides what to call, when to call it, how to respond
    - Conversation history passed every turn — Claude maintains context
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
import re
import base64
import asyncio
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import tempfile
from integrations.voice_engine import WhisperSTT, ElevenLabsTTS
from core.suggestion_engine import FALLBACK_SUGGESTIONS, FIXED_SUGGESTIONS

load_dotenv()

from gateway.logging_config import LoggingContextMiddleware, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TOKENS = 4096
TOOL_RESULT_CHAR_LIMIT = 12000

TOOL_STATUS_LABELS = {
    "get_financial_report"    : "Loading financial report...",
    "get_project_expenses"    : "Loading project expenses...",
    "get_project_financial_data": "Loading project financial data...",
    "get_general_ledger"      : "Loading general ledger...",
    "get_trial_balance"       : "Loading trial balance...",
    "query_accounting"        : "Running accounting report...",
    "get_partner_ageing"      : "Loading partner ageing...",
    "get_partner_ledger"      : "Loading partner ledger...",
    "get_projects_summary"    : "Finding projects...",
    "get_purchase_orders"     : "Looking up purchase orders...",
    "get_top_projects_by_metric": "Ranking projects...",
    "get_project_cost_categories": "Breaking down project costs...",
    "get_project_expense_summary": "Loading project expense summary...",
    "get_project_expense_breakdown": "Loading GL expense breakdown...",
    "compare_project_expenses": "Comparing project expenses...",
    "get_period_comparison"   : "Comparing periods...",
    "get_projects_with_overrun": "Checking budget overruns...",
    "get_projects_by_client"  : "Finding client projects...",
    "get_project_counts_by_client": "Grouping projects by client...",
    "group_and_aggregate"     : "Grouping and aggregating records...",
    "sql_aggregate"           : "Synthesizing analytics...",
    "compose_report"          : "Structuring report...",
    "calculate"               : "Calculating metrics...",
    "generate_pdf_report"     : "Generating PDF report...",
    "synthesize_pdf"          : "Generating PDF report...",
    "search_odoo"             : "Gathering records...",
    "search_entities"         : "Searching for matching records...",
    "get_my_payslips"         : "Loading your payslips...",
    "get_employee_payslips"   : "Loading employee payslips...",
    "list_recent_payslips"    : "Listing recent payslips...",
}

TOOL_SUGGESTIONS = {
    "get_project_expenses": FIXED_SUGGESTIONS[
        ("KPI", "project.financial.service", "get_project_expense_dashboard")
    ],
    "get_project_financial_data": FIXED_SUGGESTIONS[
        ("KPI", "project.financial.service", "get_project_financial_data")
    ],
    "get_financial_report": FIXED_SUGGESTIONS[
        ("ACCOUNTING", "ins.financial.report", "get_report_values")
    ],
    "get_general_ledger": FIXED_SUGGESTIONS[
        ("ACCOUNTING", "ins.general.ledger", "get_report_datas")
    ],
    "get_partner_ageing": FIXED_SUGGESTIONS[
        ("ACCOUNTING", "ins.partner.ageing", "get_report_datas")
    ],
    "get_projects_summary": FIXED_SUGGESTIONS[
        ("RAG", "project.project", None)
    ],
    "get_purchase_orders": [
        "Show the latest 10 purchase orders for this client",
        "Show expense details for the first project",
        "Show all active projects for this client",
    ],
    "get_top_projects_by_metric": [
        "Show cost categories for the top project",
        "Compare this month vs last month",
        "Show projects over budget",
    ],
    "get_project_cost_categories": [
        "Show the top items in the largest category",
        "Compare this project vs last month",
        "Show active projects for this client",
    ],
    "get_period_comparison": [
        "Show profit and loss this month",
        "Show top 3 profitable projects",
        "Show projects over budget",
    ],
    "get_projects_with_overrun": [
        "Show cost categories for the first project",
        "Show active projects for this client",
        "Compare this month vs last month",
    ],
    "get_projects_by_client": [
        "Show cost categories for the first project",
        "Show purchase orders for this client",
        "Show top 3 profitable projects",
    ],
    "get_project_counts_by_client": [
        "Show projects for the top client",
        "Compare with the previous year",
        "Show purchase orders for the top client",
    ],
    "group_and_aggregate": [
        "Drill into the top group",
        "Compare with the previous period",
        "Generate a PDF report from this breakdown",
    ],
    "sql_aggregate": [
        "Generate a PDF report from this data",
        "Compare this month vs last month",
        "Show top 3 profitable projects",
    ],
    "generate_pdf_report": [
        "Generate the same report for last month",
        "Create an executive summary only",
        "Compare with the previous period",
    ],
    "search_odoo": FALLBACK_SUGGESTIONS["en"],
}


def _tool_status_label(tool_name: str, tool_input: dict | None = None) -> str:
    tool_input = tool_input or {}
    if tool_name == "search_odoo":
        model = tool_input.get("model", "")
        if model == "purchase.order":
            return "Looking up purchase orders..."
        if model == "project.project":
            return "Finding projects..."
        if model == "res.partner":
            return "Finding client records..."
        if model == "account.move":
            return "Gathering invoices..."
        return "Gathering records..."
    return TOOL_STATUS_LABELS.get(tool_name, "Preparing your answer...")


from adapters.v14.connector import OdooV14Adapter
from gateway.purchase_order_routing import (
    fetch_purchase_orders,
    prefetch_purchase_orders,
    prefetch_system_block,
    purchase_order_search_via_get_tool,
)
from gateway.project_client_grouping import (
    prefetch_projects_by_client,
    prefetch_system_block as prefetch_project_client_block,
)
from admin.api import admin_router
from admin.auth.dependencies import extract_bearer_token, require_chat_user
from admin.auth.principal import CurrentUser
from admin.rbac.context import build_user_context_prompt as build_rbac_user_prompt
from admin.rbac.context import get_request_user, set_request_user
from admin.rbac.data_scope import apply_data_scope
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.entity_gate import ConfirmedEntityRef
from gateway.intelligent_handler import IntelligentQueryHandler, IntelligentQueryResponse
from gateway.hr_identity import apply_personal_hr_scope
from admin.rbac.tool_permissions import check_tool_allowed, permission_for_tool
from admin.observability.tracking import (
    extract_token_usage,
    schedule_usage,
    track_agent_turn,
    track_pdf_generated,
    track_permission_denied,
    track_voice_minutes,
)
from gateway.auth import (
    get_profile,
    login_with_file_id,
    logout,
    refresh_tokens,
)
from gateway.conversation_store import ConversationStore
from gateway.visualization_builder import choose_response_visualization
from gateway.analytics_tools import (
    get_period_comparison,
    get_project_cost_categories,
    get_project_counts_by_client,
    get_projects_by_client,
    get_projects_with_overrun,
    get_top_projects_by_metric,
)
from gateway.tools.project_expense import (
    PROJECT_EXPENSE_TOOL_DEFINITIONS,
    PROJECT_EXPENSE_TOOL_NAMES,
    run_project_expense_tool,
)
from gateway.tools.project_profile import (
    PROJECT_PROFILE_TOOL_DEFINITIONS,
    PROJECT_PROFILE_TOOL_NAMES,
    run_project_profile_tool,
)
from gateway.tools.project_activity import (
    PROJECT_ACTIVITY_TOOL_DEFINITIONS,
    PROJECT_ACTIVITY_TOOL_NAMES,
    run_project_activity_tool,
)
from gateway.tools.project_records import (
    PROJECT_RECORDS_TOOL_DEFINITIONS,
    PROJECT_RECORDS_TOOL_NAMES,
    run_project_records_tool,
)
from gateway.tools.universal_odoo import (
    UNIVERSAL_ODOO_EXECUTORS,
    UNIVERSAL_ODOO_TOOL_DEFINITIONS,
    build_universal_context,
)
from gateway.session_entities import (
    build_session_context_prompt,
    enrich_tool_input,
    infer_scope_from_messages,
    update_scope_from_tool_result,
)
from gateway.session_scope import SessionScopeStore
from gateway.tool_cache import ToolResultCache
from gateway.tool_validation import (
    format_tool_exception,
    should_bust_cache,
    validate_tool_result,
)
from gateway.aggregate_tools import sql_aggregate
from gateway.group_aggregate_tools import group_and_aggregate
from gateway.accounting_sql.query_accounting import execute_query_accounting
from gateway.quality_formatting import (
    FIELD_LABELS,
    VALUE_LABELS,
    format_currency,
    format_percentage,
    humanize_field,
    humanize_value,
)
from gateway.quality_response import QUALITY_METRICS, polish_agent_response
from gateway.tool_input_normalization import normalize_tool_input
from gateway.query_limits import (
    apply_query_limits_to_tool_input,
    build_query_meta,
    execute_search_odoo,
    search_read_pages,
)
from gateway.compose_tools import calculate, compose_report
from gateway.pdf_reports import REPORTS_DIR, generate_pdf_report
from core.base_adapter import OdooConnectionConfig
from core.state import OdooVersion

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    from admin.auth.config import auth_db_enabled
    from admin.db.connection import close_admin_db, init_admin_db
    from gateway.api_credits import (
        run_all_credit_checks,
        start_credit_check_scheduler,
        stop_credit_check_scheduler,
    )

    if auth_db_enabled():
        try:
            await init_admin_db()
        except Exception:
            logger.exception("Admin DB init / migrations failed")

    start_credit_check_scheduler()
    try:
        await run_all_credit_checks()
    except Exception:
        logger.exception("Initial API credit check failed")
    yield
    stop_credit_check_scheduler()
    if auth_db_enabled():
        try:
            await close_admin_db()
        except Exception:
            logger.exception("Admin DB shutdown failed")


app = FastAPI(
    title   = "Odoo Omni-Agent",
    version = "3.0.0",
    docs_url= "/docs",
    lifespan= _app_lifespan,
)

from admin.security.middleware import SecurityRateLimitMiddleware
from gateway.metrics import (
    PrometheusMetricsMiddleware,
    ai_streaming_connections,
    chat_stream_duration,
    metrics_content_type,
    metrics_payload,
    record_ai_query,
    record_claude_response,
    record_tool_execution,
)
from starlette.responses import Response as StarletteResponse

app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(SecurityRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    expose_headers    = [
        "X-Request-ID",
        "X-Session-Id",
        "X-Language",
        "X-Transcript",
        "X-Response",
        "X-Transcript-B64",
        "X-Response-B64",
    ],
)
app.add_middleware(LoggingContextMiddleware)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
app.include_router(admin_router)

from visualize.router import router as visualize_router

app.include_router(visualize_router)

_http_bearer = HTTPBearer(auto_error=False)
# ← ADD HERE — Voice engines (lazy loaded)
_stt: WhisperSTT | None = None
_tts: ElevenLabsTTS | None = None

def get_stt() -> WhisperSTT:
    global _stt
    if _stt is None:
        _stt = WhisperSTT()
    return _stt

def get_tts() -> ElevenLabsTTS:
    global _tts
    if _tts is None:
        _tts = ElevenLabsTTS()
    return _tts


def _ascii_header(value: str, *, max_length: int = 4000) -> str:
    sanitized = re.sub(r"[\x00-\x1f\x7f]+", " ", value or "")
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    sanitized = sanitized.encode("ascii", errors="ignore").decode("ascii").strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[: max_length - 3].rstrip() + "..."
    return sanitized


def _utf8_header(value: str, *, max_length: int = 4000) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", " ", text).strip()
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


_agent_client: anthropic.Anthropic | None = None


def get_agent_client() -> anthropic.Anthropic:
    global _agent_client
    if _agent_client is None:
        _agent_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _agent_client


class StreamTextFilter:
    """Suppress visualization JSON, clarify blocks, and viz hints while streaming."""

    _ORPHAN_VIZ_RE = re.compile(
        r'(?:\n|^)\s*(?:\{\s*)?"visual_type"\s*:',
        re.IGNORECASE,
    )
    _VIZ_HINT_RE = re.compile(
        r"<viz-hint>\s*([^<]+?)\s*</viz-hint>",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._pending = ""
        self._in_visualization = False
        self._in_clarify = False
        self._clarify_buffer = ""
        self.viz_hint: str | None = None
        self.clarification: dict | None = None

    def _strip_viz_hints(self, text: str) -> str:
        def _capture(match: re.Match[str]) -> str:
            self.viz_hint = match.group(1).strip().upper()
            return ""

        return self._VIZ_HINT_RE.sub(_capture, text)

    def push(self, chunk: str) -> str:
        if not chunk:
            return ""

        text = self._pending + chunk
        self._pending = ""
        visible = []

        while text:
            if self._in_clarify:
                end = text.find("</clarify>")
                if end == -1:
                    self._clarify_buffer += text
                    self._pending = ""
                    break
                self._clarify_buffer += text[:end]
                from gateway.clarify import parse_clarify_block

                wrapped = f"<clarify>{self._clarify_buffer}</clarify>"
                self.clarification = parse_clarify_block(wrapped)
                self._clarify_buffer = ""
                self._in_clarify = False
                text = text[end + len("</clarify>"):]
                continue

            if self._in_visualization:
                end = text.find("</visualization>")
                if end == -1:
                    self._pending = text
                    break
                text = text[end + len("</visualization>"):]
                self._in_visualization = False
                continue

            clarify_start = text.find("<clarify>")
            viz_start = text.find("<visualization>")
            if clarify_start != -1 and (viz_start == -1 or clarify_start < viz_start):
                if clarify_start:
                    visible.append(text[:clarify_start])
                text = text[clarify_start + len("<clarify>"):]
                self._in_clarify = True
                self._clarify_buffer = ""
                continue

            start = viz_start
            if start == -1:
                start = text.find("<visualization>")
            if start == -1:
                orphan = self._ORPHAN_VIZ_RE.search(text)
                if orphan:
                    if orphan.start():
                        visible.append(text[:orphan.start()])
                    self._pending = text[orphan.start():]
                    self._in_visualization = True
                    break
                visible.append(text)
                text = ""
                break

            if start:
                visible.append(text[:start])
            text = text[start + len("<visualization>"):]
            self._in_visualization = True

        return self._strip_viz_hints("".join(visible))


def _strip_visualization_markup(text: str) -> str:
    from gateway.clarify import strip_clarify_markup

    cleaned = strip_clarify_markup(text or "")
    cleaned = re.sub(
        r"<viz-hint>\s*[^<]+?\s*</viz-hint>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    if "<visualization>" in cleaned:
        cleaned = cleaned[:cleaned.index("<visualization>")].strip()
    cleaned = re.sub(r"</visualization>\s*", "", cleaned)
    cleaned = re.sub(
        r'\{\s*"visual_type"[\s\S]*?(?:\}\s*</visualization>|\}\s*$)',
        "",
        cleaned,
    )
    cleaned = re.sub(
        r'(?:\n|^)\s*(?:\{\s*)?"visual_type"\s*:[\s\S]*$',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\n\*\*Suggestions:\*\*[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Odoo Adapter Factory
# ---------------------------------------------------------------------------

def get_adapter() -> OdooV14Adapter:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    return get_shared_odoo_adapter()

# ---------------------------------------------------------------------------
# Tool Definitions (Claude function calling)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name"       : "get_financial_report",
        "description": (
            "Get financial reports: Profit & Loss, Balance Sheet, or Cash Flow. "
            "Use this for company-wide financial data — NOT for specific projects. "
            "Supports English and Arabic queries."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "report_type": {
                    "type"       : "string",
                    "enum"       : ["pandl", "balance_sheet", "cash_flow"],
                    "description": "pandl=Profit & Loss, balance_sheet=Balance Sheet, cash_flow=Cash Flow",
                },
                "date_from": {
                    "type"       : "string",
                    "description": "Start date YYYY-MM-DD. Default: first day of current month",
                },
                "date_to": {
                    "type"       : "string",
                    "description": "End date YYYY-MM-DD. Default: today",
                },
            },
            "required": ["report_type"],
        },
    },
    {
        "name"       : "get_project_expenses",
        "description": (
            "LEGACY expense dashboard for ONE project (weekly trend dashboard API). "
            "Prefer get_project_expense_summary for expense overview (W.O, spend %, top trades). "
            "Do NOT use for GL drill-down; use get_project_expense_breakdown."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "project_name": {
                    "type"       : "string",
                    "description": "Project name in English or Arabic",
                },
                "project_id": {
                    "type"       : "integer",
                    "description": "Project ID if known",
                },
            },
        },
    },
    
    {
        "name"       : "get_partner_ledger",
        "description": "Get Partner Ledger — transaction history per customer/vendor.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "date_from"       : {"type": "string"},
                "date_to"         : {"type": "string"},
                "result_selection": {"type": "string", "enum": ["customer", "supplier", "customer_supplier"]},
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name"       : "get_project_financial_data",
        "description": (
            "Get project P&L for ONE specific project with a date range: income, expense, "
            "net profit, and margin. Use for profitability questions about a named project. "
            "Do NOT use for category breakdowns or top-N rankings."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "project_name": {
                    "type"       : "string",
                    "description": "Project name",
                },
                "project_id": {
                    "type"       : "integer",
                    "description": "Project ID if known",
                },
                "date_from": {
                    "type"       : "string",
                    "description": "Start date YYYY-MM-DD",
                },
                "date_to": {
                    "type"       : "string",
                    "description": "End date YYYY-MM-DD",
                },
            },
        },
    },
    {
        "name"       : "get_general_ledger",
        "description": (
            "Get General Ledger — all account transactions with debit, credit, balance. "
            "Use for detailed account-level financial data."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "date_from": {
                    "type"       : "string",
                    "description": "Start date YYYY-MM-DD",
                },
                "date_to": {
                    "type"       : "string",
                    "description": "End date YYYY-MM-DD",
                },
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name"       : "query_accounting",
        "description": (
            "Primary financial reporting tool using direct PostgreSQL against Odoo "
            "account.move.line. Use for trial balance, P&L, balance sheet, general "
            "ledger, partner ageing, and cost analysis. Prefer this over sql_aggregate "
            "for official financial statements."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": [
                        "trial_balance",
                        "pandl",
                        "balance_sheet",
                        "general_ledger",
                        "partner_ageing",
                        "cost_analysis",
                    ],
                },
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "as_of_date": {"type": "string"},
                "result_selection": {
                    "type": "string",
                    "description": "For partner_ageing: customer (receivable) or supplier (payable)",
                },
                "company_id": {"type": "integer", "default": 1},
                "limit": {"type": "integer", "default": 5000},
            },
            "required": ["report_type"],
        },
    },
    {
        "name"       : "get_trial_balance",
        "description": "Get Trial Balance — summary of all accounts with debit, credit, balance totals.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "date_from": {
                    "type"       : "string",
                    "description": "Start date YYYY-MM-DD",
                },
                "date_to": {
                    "type"       : "string",
                    "description": "End date YYYY-MM-DD",
                },
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name"       : "get_projects_summary",
        "description": (
            "List active projects without ranking or financial comparison. "
            "Use only when the user wants a project directory. "
            "Do NOT use for top profitable projects, overruns, or client financial rollups."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "limit": {
                    "type"       : "integer",
                    "description": "Max projects to return. Default 20.",
                },
            },
        },
    },
    {
        "name"       : "get_top_projects_by_metric",
        "description": (
            "Rank the top N projects by a financial metric using real Odoo data. "
            "Use for top profitable projects, most expensive projects, best margin, "
            "or biggest budget overrun. Do NOT invent project names or numbers."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "metric": {
                    "type"       : "string",
                    "enum"       : [
                        "net_profit",
                        "revenue",
                        "total_cost",
                        "budget_overrun",
                        "margin_percent",
                    ],
                    "description": "Metric to rank by",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "How many projects to return. Default 5.",
                },
                "order": {
                    "type"       : "string",
                    "enum"       : ["desc", "asc"],
                    "description": "Sort order. Default desc.",
                },
                "date_from": {"type": "string"},
                "date_to"  : {"type": "string"},
            },
            "required": ["metric"],
        },
    },
    {
        "name"       : "get_project_cost_categories",
        "description": (
            "Get a categorized cost breakdown for ONE project: LPO, Petty Cash, Labor, "
            "Staff, Materials, and related categories. Use for follow-ups like "
            "categorize the expenses, break down by type, or drill into categories. "
            "Do NOT reuse get_project_expenses when the user asks for category detail."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "project_id"  : {"type": "integer"},
                "project_name": {"type": "string"},
                "date_from"   : {"type": "string"},
                "date_to"     : {"type": "string"},
            },
        },
    },
    {
        "name"       : "get_period_comparison",
        "description": (
            "Compare company financial metrics between two periods. "
            "Use for this month vs last month or quarter-over-quarter questions."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["pandl", "expenses", "revenue"],
                },
                "period_1_from": {"type": "string"},
                "period_1_to"  : {"type": "string"},
                "period_1_label": {"type": "string"},
                "period_2_from": {"type": "string"},
                "period_2_to"  : {"type": "string"},
                "period_2_label": {"type": "string"},
            },
            "required": [
                "report_type",
                "period_1_from",
                "period_1_to",
                "period_2_from",
                "period_2_to",
            ],
        },
    },
    {
        "name"       : "get_projects_with_overrun",
        "description": (
            "List projects that are over budget or above a budget usage threshold. "
            "Use for which projects are over budget or at risk."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "threshold_percent": {
                    "type"       : "number",
                    "description": "Minimum budget usage percent to include. Default 100.",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "Maximum projects to return. Default 10.",
                },
            },
        },
    },
    {
        "name"       : "get_projects_by_client",
        "description": (
            "List projects for a specific client or partner, optionally with financial KPIs. "
            "Use when the user asks for all projects for a client."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "client_name": {"type": "string"},
                "client_id"  : {"type": "integer"},
                "include_financials": {
                    "type"       : "boolean",
                    "description": "Attach project expense KPIs when true.",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "Maximum projects to return. Default 20.",
                },
            },
        },
    },
    {
        "name"       : "get_project_counts_by_client",
        "description": (
            "Count projects grouped by client for a year or date range using Odoo read_group. "
            "Use for questions like projects by client in 2024. "
            "Prefer this over sql_aggregate or search_odoo for client project counts."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "year": {
                    "type"       : "integer",
                    "description": "Calendar year, e.g. 2024.",
                },
                "date_from": {
                    "type"       : "string",
                    "description": "Start date YYYY-MM-DD.",
                },
                "date_to": {
                    "type"       : "string",
                    "description": "End date YYYY-MM-DD.",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "Maximum client groups to return. Default 100.",
                },
            },
        },
    },
    {
        "name"       : "get_partner_ageing",
        "description": (
            "Get Partner Ageing report — outstanding amounts by age buckets "
            "(0-30, 31-60, 61-90, 90+ days). Use for receivables/payables analysis."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "result_selection": {
                    "type"       : "string",
                    "enum"       : ["customer", "supplier", "customer_supplier"],
                    "description": "customer=receivables, supplier=payables",
                },
                "date_from": {
                    "type"       : "string",
                    "description": "As of date YYYY-MM-DD. Default: today",
                },
            },
        },
    },
    {
        "name"       : "get_purchase_orders",
        "description": (
            "Get recent purchase orders for a client or project. "
            "Use client_name when the user mentions a customer/client company. "
            "Use partner_ids when client res.partner IDs are already known. "
            "On purchase.order, partner_id is the supplier/vendor and the client "
            "is stored on a separate client field. "
            "Use project_name or project_id when the project is already known. "
            "Includes locked, approved, and completed purchase orders."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "client_name": {
                    "type"       : "string",
                    "description": "Client/customer company name",
                },
                "partner_ids": {
                    "type"       : "array",
                    "description": "Known res.partner IDs for the client",
                    "items"      : {"type": "integer"},
                },
                "project_name": {
                    "type"       : "string",
                    "description": "Project name if known",
                },
                "project_id": {
                    "type"       : "integer",
                    "description": "Project ID if known",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "How many purchase orders to return. Default 20.",
                },
            },
        },
    },
    {
        "name"       : "group_and_aggregate",
        "description": (
            "Query any Odoo model with filters, grouping, and aggregation using read_group. "
            "Use for group by, breakdown, totals per dimension, top-N grouped results, "
            "and pivot-style analysis. Do not iterate records manually with search_odoo."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "model": {
                    "type"       : "string",
                    "description": "Odoo model such as project.project or account.move.",
                },
                "domain": {
                    "type"       : "array",
                    "description": "Odoo domain filter as a list of tuples.",
                    "items"      : {},
                },
                "group_by": {
                    "type"       : "array",
                    "items"      : {"type": "string"},
                    "description": "Fields to group by, e.g. partner_id or date:month.",
                },
                "aggregates": {
                    "type"       : "array",
                    "items"      : {"type": "string"},
                    "description": "Aggregate specs such as amount_total:sum or id:count.",
                },
                "order_by": {
                    "type"       : "string",
                    "description": "Sort grouped results, e.g. amount_total:sum desc.",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "Maximum groups to return. Default 50, max 200.",
                },
                "having": {
                    "type"       : "object",
                    "description": "Post-aggregation filter such as {'balance:sum': ['>', 1000]}.",
                },
            },
            "required": ["model", "group_by"],
        },
    },
    {
        "name"       : "sql_aggregate",
        "description": (
            "Aggregate Odoo records with read_group when no direct report tool exists. "
            "Use for trial balance synthesis and custom groupings. "
            "For project counts by client in a period, use get_project_counts_by_client. "
            "When ordering grouped results, use partner_id_count or __count, not partner_id:count."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "model": {"type": "string"},
                "filters": {"type": "array", "items": {}},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "aggregates": {"type": "array", "items": {"type": "string"}},
                "having": {"type": "object"},
                "order": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["model", "aggregates"],
        },
    },
    {
        "name"       : "compose_report",
        "description": (
            "Structure raw rows into a report payload with headers, rows, and totals. "
            "Use after sql_aggregate or search_odoo when the user wants a formatted report."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "date_range": {"type": "string"},
                "report_type": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {}},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name"       : "calculate",
        "description": (
            "Run deterministic math on values already fetched from Odoo. "
            "Supports sum, average, median, min, max, count, percent change, ratio, and difference."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "op": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["op", "values"],
                    },
                },
            },
            "required": ["operations"],
        },
    },
    {
        "name"       : "synthesize_pdf",
        "description": (
            "Generate a downloadable PDF from a JSON section specification. "
            "Alias of generate_pdf_report for composed or synthesized report output."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "date_range": {"type": "string"},
                "language": {"type": "string", "enum": ["en", "ar"]},
                "theme": {"type": "string", "enum": ["light", "dark"]},
                "sections": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["title", "sections"],
        },
    },
    {
        "name"       : "generate_pdf_report",
        "description": (
            "Generate a downloadable PDF report from a JSON section specification. "
            "Use when the user asks for PDF, export, download, print, or executive summary."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "date_range": {"type": "string"},
                "language": {"type": "string", "enum": ["en", "ar"]},
                "theme": {"type": "string", "enum": ["light", "dark"]},
                "sections": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["title", "sections"],
        },
    },
    {
        "name"       : "search_odoo",
        "description": (
            "Search Odoo records for projects, invoices, employees, customers, "
            "and partners. Do not use this tool to list purchase orders by client; "
            "use get_purchase_orders instead."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "model": {
                    "type"       : "string",
                    "description": "Odoo model: project.project, account.move, hr.employee, res.partner, etc.",
                },
                "filters": {
                    "type"       : "array",
                    "description": "Odoo domain filters e.g. [['state','=','posted']]",
                    "items"      : {},
                },
                "fields": {
                    "type"       : "array",
                    "description": "Fields to return e.g. ['name','amount_total','state']",
                    "items"      : {"type": "string"},
                },
                "limit": {
                    "type"       : "integer",
                    "description": (
                        "Max records to return. If omitted, the server applies a role-based "
                        "default (up to 2000 for super admin). Response includes _query_meta "
                        "with total_matching and truncated flags."
                    ),
                },
                "order": {
                    "type"       : "string",
                    "description": "Sort order e.g. 'date desc'",
                },
                "_scope_self": {
                    "type"       : "boolean",
                    "description": (
                        "If true, restrict HR models to the signed-in user's employee "
                        "(File ID = emp_id). Use for my payslip, my leave, my tasks."
                    ),
                },
            },
            "required": ["model", "fields"],
        },
    },
    {
        "name"       : "get_my_payslips",
        "description": (
            "Get payslips for the currently logged-in user (my payslip, my salary, last payslip). "
            "Resolves hr.employee from File ID / Odoo user link. Always use this instead of search_odoo "
            "for personal payslip questions."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "limit": {
                    "type"       : "integer",
                    "description": "How many recent payslips (default 5, max 20).",
                },
            },
        },
    },
    {
        "name"       : "get_employee_payslips",
        "description": (
            "Payslips for a specific employee by File ID / emp_id. "
            "Use for HR/admin viewing another person's payroll. Requires permission; "
            "omit employee_file_id only when asking about yourself (use get_my_payslips)."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "employee_file_id": {
                    "type"       : "string",
                    "description": "Employee File ID / emp_id (e.g. 2721).",
                },
                "limit": {
                    "type"       : "integer",
                    "description": "Max payslips to return (default 5).",
                },
            },
            "required": ["employee_file_id"],
        },
    },
    {
        "name"       : "list_recent_payslips",
        "description": (
            "List recent payslips in Odoo (any employee). Use when the user asks for "
            "'any payslip', 'show payslips', or HR payroll browse — not for a specific person "
            "(use get_employee_payslips with employee_file_id). Requires HR/admin access."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "limit": {
                    "type"       : "integer",
                    "description": "Max payslips (default 10, max 50).",
                },
            },
        },
    },
    *PROJECT_EXPENSE_TOOL_DEFINITIONS,
    *PROJECT_PROFILE_TOOL_DEFINITIONS,
    *PROJECT_RECORDS_TOOL_DEFINITIONS,
    *PROJECT_ACTIVITY_TOOL_DEFINITIONS,
    *UNIVERSAL_ODOO_TOOL_DEFINITIONS,
    {
        "name": "search_entities",
        "description": (
            "Search for project or partner candidates by name when the user wants to "
            "find or list matching records before fetching financial data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Entity type to search (currently project).",
                },
                "query": {
                    "type": "string",
                    "description": "Natural-language name or phrase to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum candidates to return (default 10).",
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum match confidence (default 0.3).",
                },
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Executor
# ---------------------------------------------------------------------------

def execute_tool(
    tool_name  : str,
    tool_input : dict,
    adapter    : OdooV14Adapter,
    session_id : str | None = None,
    user_message: str = "",
) -> Any:
    """Executes a tool call and returns the result."""
    started = time.perf_counter()
    tool_input = dict(tool_input or {})
    status = "success"
    cached = False
    result: Any = None

    try:
        user = get_request_user()
        cache_user_id = user.id if user is not None else "anon"
        if user is not None:
            denied = check_tool_allowed(user, tool_name, tool_input)
            if denied:
                status = "denied"
                result = {"error": denied, "permission_denied": True}
                return result
            tool_input = apply_data_scope(tool_input, user)
            if adapter is not None:
                tool_input = apply_personal_hr_scope(tool_name, tool_input, user, adapter)
        tool_input = enrich_tool_input(tool_name, tool_input, session_id)
        if tool_input.get("_hr_scope_error"):
            return {
                "error": tool_input["_hr_scope_error"],
                "permission_denied": False,
            }
        tool_input = normalize_tool_input(tool_name, tool_input)
        if user is not None:
            tool_input = apply_query_limits_to_tool_input(tool_name, tool_input, user)
        from gateway.date_utils import enforce_date_range

        tool_input = enforce_date_range(tool_name, tool_input)
        date_was_defaulted = bool(tool_input.pop("_date_was_defaulted", False))

        if should_bust_cache(user_message):
            ToolResultCache.delete(tool_name, tool_input, cache_user_id)
        else:
            cached_result = ToolResultCache.get(tool_name, tool_input, cache_user_id)
            if cached_result is not None:
                cached = True
                result = validate_tool_result(tool_name, cached_result)
                update_scope_from_tool_result(session_id, tool_name, tool_input, result)
                if isinstance(result, dict) and result.get("error"):
                    status = "error"
                logger.info(
                    "[TOOL] %s",
                    json.dumps({
                        "tool": tool_name,
                        "cached": True,
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                        "result_has_error": bool(isinstance(result, dict) and result.get("error")),
                    }),
                )
                return result

        logger.info("[Tool] %s(%s)", tool_name, tool_input)

        if tool_name == "get_financial_report":
            result = adapter.accounting.get_financial_report(
                report_type = tool_input.get("report_type", "pandl"),
                date_from   = tool_input.get("date_from"),
                date_to     = tool_input.get("date_to"),
            )
        elif tool_name == "get_trial_balance":
            result = adapter.accounting.get_trial_balance(
                date_from = tool_input.get("date_from"),
                date_to   = tool_input.get("date_to"),
            )
        elif tool_name == "query_accounting":
            result = execute_query_accounting(tool_input, adapter=adapter)
        elif tool_name == "get_projects_summary":
            domain = [["active", "=", True]]
            limit = int(tool_input.get("limit") or 100)
            fields = [
                "id",
                "name",
                "partner_id",
                "user_id",
                "wo_ref_no",
                "date_start",
                "date",
                "stage_id",
            ]
            projects = search_read_pages(
                adapter,
                model="project.project",
                domain=domain,
                fields=fields,
                limit=limit,
                order="name asc",
            )
            total = None
            try:
                total = adapter.search_count("project.project", domain)
            except Exception:
                pass
            result = {
                "projects": projects,
                "_query_meta": build_query_meta(
                    returned_count=len(projects),
                    limit_applied=limit,
                    total_matching=total,
                    limit_meta=tool_input.get("_limit_meta"),
                    user=user,
                    model="project.project",
                ),
                "note": (
                    "For project expense overview, use get_project_expense_summary with project_id. "
                    "For filtered lists (e.g. in progress), use search_odoo on project.project "
                    "with stage/state filters — not only get_projects_summary."
                ),
            }
        elif tool_name == "get_partner_ageing":
            result = adapter.accounting.get_partner_ageing(
                date_from=tool_input.get("date_from"),
                date_to=tool_input.get("date_to"),
                as_of_date=tool_input.get("as_of_date"),
                result_selection=tool_input.get("result_selection", "customer"),
                partner_ids=tool_input.get("partner_ids"),
                company_id=int(tool_input.get("company_id", 1)),
                operating_unit_ids=tool_input.get("operating_unit_ids"),
            )
        elif tool_name == "get_partner_ledger":
            result = adapter.call_method(
                "project.financial.service",
                "get_ai_partner_ledger",
                [
                    tool_input.get("date_from"),
                    tool_input.get("date_to"),
                    tool_input.get("result_selection", "customer_supplier"),
                ],
            )
        elif tool_name == "get_project_expenses":
            from core.base_adapter import KPIRequest
            from adapters.v14.connector import ProjectAmbiguousError, ProjectNotFoundError

            request = KPIRequest(
                kpi_type = "expense_dashboard",
                model    = "project.financial.service",
                method   = "get_project_expense_dashboard",
                filters  = {
                    "project_id"  : tool_input.get("project_id"),
                    "project_name": tool_input.get("project_name"),
                },
            )
            try:
                response = adapter.get_kpi_data(request)
                result = response.raw_data
            except ProjectAmbiguousError as exc:
                candidates = []
                for c in exc.candidates:
                    candidates.append({
                        "id"       : c.get("id"),
                        "name"     : c.get("name"),
                        "wo_ref_no": c.get("wo_ref_no"),
                        "client"   : c.get("partner_id")[1] if isinstance(c.get("partner_id"), list) else c.get("partner_id"),
                    })
                result = {
                    "error"     : "multiple_projects_found",
                    "message"   : f"Found {len(candidates)} projects matching your search.",
                    "candidates": candidates,
                }
            except ProjectNotFoundError as exc:
                result = {
                    "error"  : "project_not_found",
                    "message": f"No project found matching '{exc.search_term}'. Please provide the WO reference number or full project name.",
                }
        elif tool_name == "get_project_financial_data":
            from core.base_adapter import KPIRequest
            from adapters.v14.connector import ProjectAmbiguousError, ProjectNotFoundError

            request = KPIRequest(
                kpi_type   = "financial_data",
                model      = "project.financial.service",
                method     = "get_project_financial_data",
                filters    = {
                    "project_id"  : tool_input.get("project_id"),
                    "project_name": tool_input.get("project_name"),
                    "date_from"   : tool_input.get("date_from"),
                    "date_to"     : tool_input.get("date_to"),
                },
            )
            try:
                response = adapter.get_kpi_data(request)
                result = response.raw_data
            except ProjectAmbiguousError as exc:
                candidates = []
                for c in exc.candidates:
                    candidates.append({
                        "id"       : c.get("id"),
                        "name"     : c.get("name"),
                        "wo_ref_no": c.get("wo_ref_no"),
                        "client"   : c.get("partner_id")[1] if isinstance(c.get("partner_id"), list) else c.get("partner_id"),
                    })
                result = {
                    "error"     : "multiple_projects_found",
                    "message"   : f"Found {len(candidates)} projects matching your search.",
                    "candidates": candidates,
                }
            except ProjectNotFoundError as exc:
                result = {
                    "error"  : "project_not_found",
                    "message": f"No project found matching '{exc.search_term}'. Please provide the WO reference number or full project name.",
                }
        elif tool_name == "get_general_ledger":
            result = adapter.accounting.get_general_ledger(
                date_from = tool_input.get("date_from"),
                date_to   = tool_input.get("date_to"),
            )
        elif tool_name == "get_top_projects_by_metric":
            result = get_top_projects_by_metric(adapter, tool_input)
        elif tool_name == "get_project_cost_categories":
            result = get_project_cost_categories(adapter, tool_input, session_id)
        elif tool_name in PROJECT_EXPENSE_TOOL_NAMES:
            result = run_project_expense_tool(tool_name, tool_input, adapter)
        elif tool_name in PROJECT_PROFILE_TOOL_NAMES:
            result = run_project_profile_tool(tool_name, tool_input, adapter)
        elif tool_name in PROJECT_RECORDS_TOOL_NAMES:
            result = run_project_records_tool(tool_name, tool_input, adapter)
        elif tool_name in PROJECT_ACTIVITY_TOOL_NAMES:
            result = run_project_activity_tool(tool_name, tool_input, adapter)
        elif tool_name == "get_period_comparison":
            result = get_period_comparison(adapter, tool_input)
        elif tool_name == "get_projects_with_overrun":
            result = get_projects_with_overrun(adapter, tool_input)
        elif tool_name == "get_projects_by_client":
            result = get_projects_by_client(adapter, tool_input)
        elif tool_name == "get_project_counts_by_client":
            result = get_project_counts_by_client(adapter, tool_input)
        elif tool_name == "group_and_aggregate":
            result = group_and_aggregate(adapter, tool_input)
        elif tool_name == "get_purchase_orders":
            result = fetch_purchase_orders(
                adapter,
                client_name  = tool_input.get("client_name"),
                partner_ids  = tool_input.get("partner_ids"),
                project_name = tool_input.get("project_name"),
                project_id   = tool_input.get("project_id"),
                limit        = tool_input.get("limit", 20),
                session_id   = session_id,
            )
        elif tool_name == "sql_aggregate":
            result = sql_aggregate(adapter, tool_input)
        elif tool_name == "compose_report":
            result = compose_report(tool_input)
        elif tool_name == "calculate":
            result = calculate(tool_input)
        elif tool_name in {"generate_pdf_report", "synthesize_pdf"}:
            result = generate_pdf_report(tool_input, session_id=session_id)
        elif tool_name == "search_entities":
            import asyncio

            from gateway.tools.search_entities import execute_search_entities, minimal_search_context

            result = asyncio.run(
                execute_search_entities(
                    adapter,
                    tool_input,
                    minimal_search_context(user_message=user_message),
                ),
            )
        elif tool_name == "search_odoo":
            if tool_input.get("model") == "purchase.order":
                result = purchase_order_search_via_get_tool(adapter, tool_input)
            else:
                result = execute_search_odoo(adapter, tool_input, user)
        elif tool_name == "get_my_payslips":
            import asyncio

            from gateway.hr_payroll_tools import get_my_payslips

            chat_user = get_request_user()
            if chat_user is None:
                result = {"error": "not_authenticated", "payslips": []}
            else:
                result = asyncio.run(
                    get_my_payslips(
                        adapter,
                        chat_user,
                        limit=tool_input.get("limit", 5),
                    )
                )
        elif tool_name == "get_employee_payslips":
            import asyncio

            from gateway.hr_payroll_tools import get_employee_payslips

            chat_user = get_request_user()
            if chat_user is None:
                result = {"error": "not_authenticated", "payslips": []}
            else:
                result = asyncio.run(
                    get_employee_payslips(
                        adapter,
                        chat_user,
                        employee_file_id=tool_input.get("employee_file_id", ""),
                        limit=tool_input.get("limit", 5),
                    )
                )
        elif tool_name == "list_recent_payslips":
            import asyncio

            from gateway.hr_payroll_tools import list_recent_payslips

            chat_user = get_request_user()
            if chat_user is None:
                result = {"error": "not_authenticated", "payslips": []}
            else:
                result = asyncio.run(
                    list_recent_payslips(
                        adapter,
                        chat_user,
                        limit=tool_input.get("limit", 10),
                    )
                )
        elif tool_name in UNIVERSAL_ODOO_EXECUTORS:
            import asyncio

            chat_user = get_request_user()
            context = build_universal_context(
                user_message=user_message,
                user=chat_user,
            )
            result = asyncio.run(
                UNIVERSAL_ODOO_EXECUTORS[tool_name](adapter, tool_input, context),
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        if isinstance(result, dict) and result.get("error"):
            status = "error"

        if isinstance(result, dict) and not result.get("error"):
            if tool_input.get("date_from"):
                result["date_from"] = tool_input["date_from"]
            if tool_input.get("date_to"):
                result["date_to"] = tool_input["date_to"]
            if date_was_defaulted:
                result["_date_was_defaulted"] = True
            ToolResultCache.set(tool_name, tool_input, result, cache_user_id)

        result = validate_tool_result(tool_name, result)
        update_scope_from_tool_result(session_id, tool_name, tool_input, result)
        logger.info(
            "[TOOL] %s",
            json.dumps({
                "tool": tool_name,
                "cached": cached,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "result_has_error": bool(isinstance(result, dict) and result.get("error")),
            }),
        )
        return result

    except Exception as exc:
        status = "error"
        logger.error("[Tool] %s failed: %s", tool_name, exc)
        result = format_tool_exception(exc)
        result = validate_tool_result(tool_name, result)
        update_scope_from_tool_result(session_id, tool_name, tool_input, result)
        return result
    finally:
        record_tool_execution(
            tool_name,
            time.perf_counter() - started,
            status=status,
            cached=cached,
        )


# ---------------------------------------------------------------------------
# Claude Agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an intelligent ERP assistant for an Odoo system used by a 
Construction & Facilities Management company in UAE (Elrace).

Today's date: {today}

You have access to Odoo tools to fetch real data. Use them when needed.

UNIVERSAL READ ACCESS:
- You have universal read access to all installed Odoo models via query_odoo and
  aggregate_odoo. When a user asks about any data (employees, payroll, inventory,
  purchases, sales, fleet, timesheets, or any other module), attempt the query.
- PREFER specialized tools when they fit:
  - Financial reports → get_financial_report
  - Project expenses → get_project_expense_summary / get_project_expense_breakdown
  - Partner ageing → get_partner_ageing
  - Trial balance → get_trial_balance
- For EVERYTHING ELSE, use query_odoo or aggregate_odoo.
- If unsure which model to query, call introspect_odoo_schema.
- If no data is returned, say so honestly — do not refuse upfront.

Guidelines:
- Respond in the SAME language the user writes in (Arabic, English, or Urdu)
- Be concise and direct — answer what was asked, not the full report
- Format numbers with commas and include AED currency
- For financial reports: summarize key figures, don't dump all lines
- For project data: highlight total cost, budget status, key expenses
- If data has many items: show top 5-10 in prose but ALWAYS state total from _query_meta (returned_count / total_matching / truncated)
- Tool results may include `_query_meta`: read `summary`, `total_matching`, and `truncated` — never imply the list is complete when truncated is true
- For "all" / "every" / "in progress" list queries: use search_odoo with appropriate filters; omit limit only if you want the server default (100–2000 by role), or set limit explicitly for very large sets
- You can answer general questions (date, greetings, capabilities) directly
- For financial reports without an explicit date: the server defaults to the last 3 months (date_from/date_to injected); state the period you used in the summary
- For project queries without a project name: always ask which project
- If the user already gives a count such as "last 10" or "last 20", use that limit and do not ask again
- For purchase orders by client name, use get_purchase_orders with client_name or partner_ids. On purchase.order, partner_id is the supplier/vendor and the client is stored on a separate client field
- get_purchase_orders includes locked, approved, done, and older purchase orders; do not infer that a client has no orders from unrelated draft purchase orders
- If get_purchase_orders returns orders, describe only those rows and do not mix in unrelated purchase.order search results
- Do not use search_odoo on purchase.order for client purchase-order requests; partner_id filters are vendor/supplier filters, not client filters
- If projects for a client are already known from earlier turns, reuse those project IDs instead of asking again
- Never put numbered suggestion lists or a "Suggestions:" section in the visible answer text
- Always be helpful, professional, and accurate

Company context:
- Based in UAE, operates in Abu Dhabi and Dubai
- Construction, facilities management, maintenance projects
- Multiple projects with Arabic and English names
- Currency: AED

GROUPING AND FILTERING:
- For group by, breakdown, totals per dimension, top-N grouped results, or pivot-style analysis, use group_and_aggregate
- Never loop search_odoo over records to compute grouped totals
- Phrases such as group by, breakdown by, totals per, top N by, per client, per project, or per month signal grouping
- Projects: model project.project; common groupings partner_id, user_id, stage_id; aggregates wo_amount:sum, id:count
- Invoices and revenue: model account.move with type out_invoice and state posted; group by partner_id or date:month
- Bills and expenses: model account.move with type in_invoice and state posted
- Journal lines: model account.move.line with parent_state posted; group by account_id, partner_id, analytic_account_id, date:month
- Sales and purchase orders: model sale.order or purchase.order; group by partner_id, state, or date_order:month
- Time groupings use :day, :week, :month, :quarter, or :year on date fields
- Use limit 10 for top-N queries; for full lists the server applies role-based limits (super admin up to 2000 rows per call) — report _query_meta totals
- Sort by the aggregate descending for top queries
- For projects grouped by client in a year or date range, get_project_counts_by_client remains valid for that narrow case

DATA INTEGRITY RULES:
- Never report numbers that did not come from a tool call
- If a tool returns empty or zero data, say so explicitly and do not fabricate values
- Project names must come from Odoo records returned by tools
- For top-N project questions, use get_top_projects_by_metric instead of guessing
- For category breakdown follow-ups on a project, use get_project_cost_categories
- For project expense overview (KPIs, top trades, spend % of W.O), use get_project_expense_summary
- For GL/account drill-down on project expenses, use get_project_expense_breakdown
- To compare 2–10 projects by expense, use compare_project_expenses
- For projects grouped by client in a year or date range, use get_project_counts_by_client or group_and_aggregate instead of sql_aggregate or search_odoo
- If a tool returns an error payload, surface it instead of guessing

AUTONOMOUS PROBLEM SOLVING:
- If no direct tool exists, compose existing tools or use group_and_aggregate, sql_aggregate, or search_odoo to synthesize the answer
- Use compose_report to shape raw rows into report tables and calculate for deterministic math on fetched values
- Never say a feature is unavailable; explain what you can build from underlying Odoo data instead
- Mark synthesized answers as computed from underlying data when relevant

PRODUCTION QUALITY RULES:
- Never expose raw Odoo field syntax such as amount_total:sum or partner_id:
- Format money as AED with thousands separators
- Comparison questions must use BAR_CHART ranked by value, not nested expandable lists
- If grouped results are all zero, retry with corrected filters or explain why no data was found
- Include a 2-3 sentence narrative with the key insight when data is shown
- Use posted-only filters for financial data and company_id=1 unless the user specifies otherwise

EARLY VISUALIZATION SIGNAL:
- Before the visualization block, output this on the first line when a visualization will follow:
  <viz-hint>KPI_CARD|BAR_CHART|LINE_CHART|DATA_TABLE|GROUPED_TABLE|FINANCIAL_REPORT|PDF_REPORT|NONE</viz-hint>

IMPORTANT — VISUAL-FIRST RESPONSES:
- When any Odoo tool returns data, keep visible prose short and executive-ready
- Do not write markdown tables, bullet lists, or numbered lists in the visible answer
- Put structured values in the visualization block and use 2-3 sentences for the key insight
- Use KPI_CARD for single totals and counts
- Use DATA_TABLE for record lists such as purchase orders, projects, and invoices
- Use FINANCIAL_REPORT for P&L and balance-sheet style outputs
- Keep labels short and factual

IMPORTANT — STRUCTURED OUTPUT:
When you fetched any data, append only this visualization block (no visible prose before it):

<visualization>
{
  "visual_type": "KPI_CARD|BAR_CHART|LINE_CHART|DATA_TABLE|GROUPED_TABLE|FINANCIAL_REPORT|PDF_REPORT",
  "label": "short title",
  "value": 0,
  "unit": "AED",
  "data": {},
  "suggestions": ["follow-up question 1", "follow-up question 2", "follow-up question 3"]
}
</visualization>

Visual type rules:
- Single number (total cost, net profit, count) → KPI_CARD
- Comparison across categories (expense by type) → BAR_CHART  
- Time series (monthly trend, weekly) → LINE_CHART
- List of records (projects, invoices) → DATA_TABLE
- Hierarchical grouped breakdowns → GROUPED_TABLE
- P&L / Balance Sheet hierarchy → FINANCIAL_REPORT
- Downloadable PDF report → PDF_REPORT

PROGRESSIVE REPORT DISCLOSURE (MANDATORY for FINANCIAL_REPORT, DATA_TABLE, GROUPED_TABLE):
- Default to summary first unless the user explicitly asked for details/full breakdown
- Summary = KPIs and/or a small chart only; do not dump full account tables in summary
- Add visualization fields when data can expand:
  "level": "summary|standard|full",
  "total_records": <int>,
  "shown_records": <int>,
  "can_expand": true|false,
  "expand_label": "See all 247 accounts"
- Standard detail view = first 20 rows maximum in data.rows
- If the user asks for details, accounts, breakdown, or full report → use level "standard" or "full"
- Never return hundreds of table rows at summary level

PRE-RESPONSE CLARIFICATION (before fetching financial data):
- If the user did not specify a date range for P&L, trial balance, ledger, or similar reports,
  emit ONLY a <clarify> block (no tools, no visualization) then stop and wait.
- Format:
<clarify>
{
  "reason": "date_range_missing",
  "question": "Which time period would you like?",
  "question_ar": "أي فترة زمنية تريد؟",
  "options": [
    {"id": "this_month", "label": "This Month", "label_ar": "هذا الشهر", "query_suffix": " for this month"},
    {"id": "last_3m", "label": "Last 3 Months", "label_ar": "آخر 3 أشهر", "query_suffix": " for the last 3 months", "is_default": true},
    {"id": "ytd", "label": "This Year", "label_ar": "هذا العام", "query_suffix": " for this year"},
    {"id": "custom", "label": "Custom Range", "label_ar": "نطاق مخصص", "action": "open_date_picker"}
  ],
  "skip_option": {"label": "Skip (use last 3 months)", "label_ar": "تخطي (آخر 3 أشهر)", "query_suffix": " for the last 3 months"}
}
</clarify>
- Do NOT emit <clarify> when the user already gave dates, said skip/default, or is answering a prior clarification.

For suggestions: when any tool was used, include exactly 3 short follow-up prompts
(4-10 words each) in the SAME language as the response inside the visualization block.
Do not repeat clarification questions that the user already answered.

If no data was fetched (greetings, general questions), omit the visualization block."""

_FINANCIAL_SECTION_MARKER = "\n\nGROUPING AND FILTERING:"
_QUALITY_SECTION_MARKER = "\n\nPRODUCTION QUALITY RULES:"
_context_stack_builder = ContextStackBuilder()


class _PromptContextRequest:
    """Minimal request shape for ContextStackBuilder inside prompt assembly."""

    __slots__ = ("message", "session_id")

    def __init__(self, message: str, session_id: str | None = None) -> None:
        self.message = message
        self.session_id = session_id


def _compose_system_prompt_sections(today: str, *, context_section: str = "") -> str:
    """Assemble system prompt: core instructions, context stack, financial, quality."""
    from gateway.core.project_expense_routing import PROJECT_EXPENSE_PROMPT_SECTION
    from gateway.core.project_relationship_context import PROJECT_RELATIONSHIP_PROMPT_SECTION

    base = SYSTEM_PROMPT.replace("{today}", today)
    core, remainder = base.split(_FINANCIAL_SECTION_MARKER, 1)
    financial, quality = remainder.split(_QUALITY_SECTION_MARKER, 1)
    return (
        core
        + PROJECT_EXPENSE_PROMPT_SECTION
        + PROJECT_RELATIONSHIP_PROMPT_SECTION
        + context_section
        + _FINANCIAL_SECTION_MARKER
        + financial
        + _QUALITY_SECTION_MARKER
        + quality
    )


async def _build_agent_system_prompt(
    today        : str,
    user_message : str = "",
    adapter      : OdooV14Adapter | None = None,
    session_id   : str | None = None,
    user         : CurrentUser | None = None,
) -> str:
    context_section = ""
    context_stack = None
    if user is not None:
        context_stack = await _context_stack_builder.build(
            user,
            _PromptContextRequest(
                message=user_message or " ",
                session_id=session_id,
            ),
        )
        context_section = context_stack.to_prompt_section()

    system = _compose_system_prompt_sections(today, context_section=context_section)
    if user is not None:
        system += build_rbac_user_prompt(user)
    if context_stack is not None and user_message.strip():
        from gateway.core.intelligence_preflight import build_intelligence_preflight_section

        preflight = await build_intelligence_preflight_section(
            user_message,
            context_stack,
            adapter,
        )
        if preflight:
            system += "\n\n" + preflight
    if adapter is not None and user is not None:
        from gateway.hr_payroll_tools import build_hr_identity_prompt

        system += await build_hr_identity_prompt(user, adapter)
    if adapter is None:
        return system

    prefetch = prefetch_purchase_orders(
        adapter,
        user_message,
        session_id = session_id,
    )
    if prefetch:
        system += prefetch_system_block(prefetch)
    project_counts = prefetch_projects_by_client(adapter, user_message)
    if project_counts:
        system += prefetch_project_client_block(project_counts)
    if session_id:
        history = await ConversationStore.get(
            session_id,
            user_id=user.id if user else None,
        )
        inferred = infer_scope_from_messages(history)
        if inferred:
            SessionScopeStore.update(session_id, **inferred)
        system += build_session_context_prompt(session_id)
    return system


def _fallback_suggestions(tool_names: list[str], language: str) -> list[str]:
    lang = language if language in FALLBACK_SUGGESTIONS else "en"
    for tool_name in reversed(tool_names):
        suggestions = TOOL_SUGGESTIONS.get(tool_name)
        if suggestions:
            return suggestions[:3]
    return FALLBACK_SUGGESTIONS.get(lang, FALLBACK_SUGGESTIONS["en"])[:3]


def _normalize_suggestions(
    suggestions: list[str] | None,
    tool_names : list[str],
    language   : str,
) -> list[str]:
    cleaned: list[str] = []
    for suggestion in suggestions or []:
        text = re.sub(r"^\d+\.\s*", "", str(suggestion).strip())
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text or len(text) > 90:
            continue
        if text.endswith("?") and len(text.split()) > 14:
            continue
        cleaned.append(text)

    if cleaned:
        return cleaned[:3]

    return _fallback_suggestions(tool_names, language)


def _summarize_large_result(data: dict) -> dict:
    """Truncates large Odoo responses to prevent token overflow."""
    summary: dict[str, Any] = {}
    for key, value in data.items():
        if key == "report_lines" and isinstance(value, list):
            summary[key] = [
                line for line in value
                if line.get("level", 0) <= 2
            ][:20]
        elif key == "accounts" and isinstance(value, dict):
            items = list(value.items())[:30]
            summary[key] = {
                account_id: {
                    "name"   : account.get("name"),
                    "debit"  : account.get("debit"),
                    "credit" : account.get("credit"),
                    "balance": account.get("balance"),
                }
                for account_id, account in items
            }
        elif key == "distribution" and isinstance(value, list):
            summary[key] = value[:10]
        elif key in ("weekly_trend", "trend", "rows", "lines") and isinstance(value, list):
            summary[key] = value[:12]
        elif key == "projects" and isinstance(value, list):
            summary[key] = value[:10]
        elif key == "orders" and isinstance(value, list):
            summary[key] = value[:20]
        elif key in ("kpis", "totals", "filters",
                     "report_name", "date_from", "date_to",
                     "project_name", "exceed_percent",
                     "commitment_total", "cost_totals", "project_id"):
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = value[:10]
        elif isinstance(value, dict):
            summary[key] = dict(list(value.items())[:20])
        else:
            summary[key] = value
    return summary


def _prepare_tool_result(result: Any) -> str:
    if isinstance(result, dict):
        result = _summarize_large_result(result)

    result_str = json.dumps(result, default=str)
    if len(result_str) > TOOL_RESULT_CHAR_LIMIT:
        if isinstance(result, dict):
            result = _summarize_large_result(result)
        result_str = json.dumps(result, default=str)
    if len(result_str) > TOOL_RESULT_CHAR_LIMIT:
        result_str = result_str[:TOOL_RESULT_CHAR_LIMIT] + "..."
    return result_str


def _parse_assistant_payload(text: str) -> tuple[str, dict | None, list[str]]:
    visualization = None
    suggestions   = []
    clean_text    = _strip_visualization_markup(text)

    if "<visualization>" in text and "</visualization>" in text:
        try:
            viz_start = text.index("<visualization>") + len("<visualization>")
            viz_end   = text.index("</visualization>")
            viz_json  = text[viz_start:viz_end].strip()

            if viz_json.startswith("```"):
                viz_json = "\n".join(
                    line for line in viz_json.split("\n")
                    if not line.strip().startswith("```")
                )

            viz_data      = json.loads(viz_json)
            suggestions   = viz_data.pop("suggestions", []) or []
            visualization = viz_data
            clean_text    = _strip_visualization_markup(text[:text.index("<visualization>")])
        except Exception as exc:
            logger.warning("[Agent] Visualization parse error: %s", exc)
            clean_text = _strip_visualization_markup(text)
    else:
        raw_json = re.search(r'\{\s*"visual_type"[\s\S]*\}', text)
        if raw_json:
            try:
                viz_data      = json.loads(raw_json.group(0))
                suggestions   = viz_data.pop("suggestions", []) or []
                visualization = viz_data
                clean_text    = _strip_visualization_markup(text[:raw_json.start()])
            except Exception as exc:
                logger.warning("[Agent] Visualization JSON parse error: %s", exc)

    return clean_text, visualization, suggestions


def _finalize_agent_response(
    clean_text    : str,
    visualization : dict | None,
    suggestions   : list[str],
    tool_names    : list[str],
    tool_results  : list[Any],
    language      : str,
    user_message  : str = "",
    session_id    : str | None = None,
) -> tuple[str, dict | None, list[str], dict[str, Any] | None]:
    visualization = choose_response_visualization(
        visualization,
        tool_names,
        tool_results,
    )

    model_suggestions = _normalize_suggestions(suggestions, tool_names, language)

    from gateway.suggestion_pool import build_post_response_suggestions

    suggestions, suggestion_meta = build_post_response_suggestions(
        model_suggestions=model_suggestions,
        tool_names=tool_names,
        tool_results=tool_results,
        visualization=visualization,
        language=language,
        session_id=session_id,
    )

    clean_text, visualization = polish_agent_response(
        user_message,
        clean_text,
        visualization,
        tool_names,
        tool_results,
        language,
    )

    from gateway.tools.project_expense import PROJECT_EXPENSE_TOOL_NAMES
    from gateway.tools.project_profile import PROJECT_PROFILE_TOOL_NAMES as _PROFILE_NAMES
    from gateway.tools.project_activity import PROJECT_ACTIVITY_TOOL_NAMES as _ACTIVITY_NAMES
    from gateway.tools.project_records import PROJECT_RECORDS_TOOL_NAMES as _RECORDS_NAMES
    from gateway.visualization_builder import build_visualization_from_tool_results, is_renderable_visualization

    if visualization is None and any(
        name in PROJECT_EXPENSE_TOOL_NAMES
        or name in _PROFILE_NAMES
        or name in _RECORDS_NAMES
        or name in _ACTIVITY_NAMES
        for name in tool_names
    ):
        forced_visual = build_visualization_from_tool_results(tool_names, tool_results)
        if forced_visual and is_renderable_visualization(forced_visual):
            visualization = forced_visual
        else:
            for result in reversed(tool_results):
                if isinstance(result, dict) and result.get("_source"):
                    logger.warning(
                        "[Agent] Expense visualization build failed source=%s keys=%s",
                        result.get("_source"),
                        sorted(result.keys()),
                    )
                    break

    if visualization is None and not clean_text.strip() and tool_results:
        for result in reversed(tool_results):
            if not isinstance(result, dict) or result.get("error"):
                continue
            clients = result.get("clients") or []
            if clients:
                total_projects = sum(int(client.get("project_count") or 0) for client in clients)
                clean_text = (
                    f"Found {len(clients)} clients with {total_projects} projects "
                    f"between {result.get('date_from')} and {result.get('date_to')}."
                )
                break

    return clean_text, visualization, suggestions, suggestion_meta


def _log_agent_response(
    *,
    user_message: str,
    raw_text: str,
    clean_text: str,
    visualization: dict | None,
    suggestions: list[str],
    tool_names: list[str],
) -> None:
    logger.info(
        "[Agent] Response summary query=%r text_chars=%s clean_chars=%s visual_type=%s suggestion_count=%s tools=%s",
        user_message[:120],
        len(raw_text or ""),
        len(clean_text or ""),
        (visualization or {}).get("visual_type"),
        len(suggestions or []),
        tool_names,
    )
    if raw_text and not visualization:
        logger.warning(
            "[Agent] No visualization parsed from assistant payload preview=%r",
            (raw_text or "")[:500],
        )


async def _observe_tool_usage(block: Any, result: Any) -> None:
    user = get_request_user()
    if user is None:
        return
    if isinstance(result, dict) and result.get("permission_denied"):
        code = permission_for_tool(block.name, dict(block.input or {}))
        if code:
            schedule_usage(
                track_permission_denied(
                    user.id,
                    permission=code,
                    tool_name=block.name,
                )
            )
        return
    if block.name in {"generate_pdf_report", "synthesize_pdf"}:
        if isinstance(result, dict) and not result.get("error"):
            report_type = (block.input or {}).get("report_type")
            schedule_usage(
                track_pdf_generated(user.id, report_type=report_type)
            )


async def _execute_tool_blocks(
    blocks: list[Any],
    adapter: OdooV14Adapter,
    session_id: str | None = None,
    user_message: str = "",
) -> tuple[list[dict[str, Any]], list[str], list[Any]]:
    tool_blocks = [block for block in blocks if block.type == "tool_use"]
    if not tool_blocks:
        return [], [], []

    tool_results = []
    tool_names   = []
    raw_results  = []
    for block in tool_blocks:
        result = await asyncio.to_thread(
            execute_tool,
            block.name,
            block.input,
            adapter,
            session_id,
            user_message,
        )
        tool_names.append(block.name)
        raw_results.append(result)
        tool_results.append({
            "type"       : "tool_result",
            "tool_use_id": block.id,
            "content"    : _prepare_tool_result(result),
        })
        await _observe_tool_usage(block, result)

    return tool_results, tool_names, raw_results


def _progress_steps_for_blocks(blocks: list[Any]) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    for block in blocks:
        if block.type != "tool_use":
            continue
        steps.append({
            "id": block.id,
            "tool": block.name,
            "label": TOOL_STATUS_LABELS.get(block.name, f"Running {block.name}..."),
            "status": "queued",
        })
    return steps


async def run_agent(
    user_message: str,
    session_id  : str,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """
    Runs the Claude agent with tool use.
    Claude decides what tools to call and how to respond.
    """
    client  = get_agent_client()
    adapter = get_adapter()
    today   = datetime.now().strftime("%A, %d %B %Y")
    language = _detect_language(user_message)
    tools_used: list[str] = []
    tool_payloads: list[Any] = []

    messages = await ConversationStore.append(
        session_id, "user", user_message, user_id=user_id
    )

    logger.info(
        "[Agent] session=%s | turn=%d | input='%s'",
        session_id, len(messages), user_message[:60],
    )

    chat_user = get_request_user()

    # Agentic loop — Claude may call multiple tools
    while True:
        claude_started = time.perf_counter()
        response = client.messages.create(
            model      = AGENT_MODEL,
            max_tokens = MAX_AGENT_TOKENS,
            system     = await _build_agent_system_prompt(
                today,
                user_message,
                adapter,
                session_id,
                user=chat_user,
            ),
            tools      = TOOLS,
            messages   = messages,
        )
        record_claude_response(
            response,
            time.perf_counter() - claude_started,
            model=AGENT_MODEL,
        )

        logger.info(
            "[Agent] stop_reason=%s | usage=%s",
            response.stop_reason,
            response.usage,
        )

        # Claude finished — no more tool calls
        if response.stop_reason == "end_turn":
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            parsed_text, visualization, suggestions = _parse_assistant_payload(text)
            clean_text, visualization, suggestions, suggestion_meta = _finalize_agent_response(
                parsed_text,
                visualization,
                suggestions,
                tools_used,
                tool_payloads,
                language,
                user_message,
                session_id,
            )
            _log_agent_response(
                user_message=user_message,
                raw_text=text,
                clean_text=clean_text,
                visualization=visualization,
                suggestions=suggestions,
                tool_names=tools_used,
            )

            await ConversationStore.append(
                session_id,
                "assistant",
                clean_text,
                user_id=user_id,
                language=language,
                visualization=visualization,
                suggestions=suggestions,
            )
            history = await ConversationStore.get(session_id, user_id=user_id)

            track_uid = chat_user.id if chat_user else user_id
            if track_uid:
                inp_tok, out_tok = extract_token_usage(response)
                schedule_usage(
                    track_agent_turn(
                        track_uid,
                        input_tokens=inp_tok,
                        output_tokens=out_tok,
                        tools=tools_used,
                    )
                )

            return {
                "text"         : clean_text,
                "language"     : language,
                "visualization": visualization,
                "suggestions"  : suggestions,
                "suggestion_meta": suggestion_meta,
                "turn_number"  : len(history),
                "conversation_id": ConversationStore.conversation_id_for_session(session_id),
            }

        # Claude wants to use tools
        if response.stop_reason == "tool_use":
            messages.append({
                "role"   : "assistant",
                "content": response.content,
            })

            tool_messages, tool_names, raw_results = await _execute_tool_blocks(
                response.content,
                adapter,
                session_id,
                user_message,
            )
            tools_used.extend(tool_names)
            tool_payloads.extend(raw_results)

            messages.append({
                "role"   : "user",
                "content": tool_messages,
            })
            continue

        # Unexpected stop reason
        break

    return {
        "text"        : "I encountered an issue processing your request.",
        "language"    : language,
        "visualization": None,
        "suggestions" : _fallback_suggestions(tools_used, language) if tools_used else [],
        "turn_number" : len(
            await ConversationStore.get(session_id, user_id=user_id)
        ),
        "conversation_id": ConversationStore.conversation_id_for_session(session_id),
    }


def _detect_language(text: str) -> str:
    """Simple language detection based on script."""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    if arabic_chars > len(text) * 0.3:
        return "ar"
    return "en"


_intelligent_query_handler: IntelligentQueryHandler | None = None


def _get_intelligent_query_handler() -> IntelligentQueryHandler:
    global _intelligent_query_handler
    if _intelligent_query_handler is None:
        _intelligent_query_handler = IntelligentQueryHandler()
    return _intelligent_query_handler


async def _run_intelligent_chat(
    message: str,
    session_id: str,
    chat_user: CurrentUser,
    *,
    skip_clarification: bool = False,
    confirmed_entities: list[ConfirmedEntityRef] | None = None,
    deep_think: bool = False,
) -> IntelligentQueryResponse:
    """Run the orchestrated intelligence pipeline and persist the conversation turn."""
    user_id = chat_user.id if chat_user else None
    await ConversationStore.append(session_id, "user", message, user_id=user_id)

    adapter = get_adapter()
    language = _detect_language(message)
    result = await _get_intelligent_query_handler().handle(
        message,
        chat_user,
        adapter,
        session_id=session_id,
        language=language,
        skip_clarification=skip_clarification,
        confirmed_entities=confirmed_entities,
        deep_think=deep_think,
    )

    await ConversationStore.append(
        session_id,
        "assistant",
        result.text,
        user_id=user_id,
        language=result.language,
        visualization=result.visualization,
        suggestions=result.suggestions,
    )

    if user_id:
        schedule_usage(
            track_agent_turn(
                user_id,
                tools=result.tools_called,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

def _parse_confirmed_entities(
    payload: list[ConfirmedEntityModel] | None,
) -> list[ConfirmedEntityRef]:
    confirmed: list[ConfirmedEntityRef] = []
    for item in payload or []:
        parsed = ConfirmedEntityRef.from_dict(item.model_dump())
        if parsed is not None:
            confirmed.append(parsed)
    return confirmed


class ConfirmedEntityModel(BaseModel):
    type: str
    id: int
    name: str | None = None


class ChatRequest(BaseModel):
    message             : str
    session_id          : str | None = None
    skip_clarification  : bool = False
    confirmed_entities  : list[ConfirmedEntityModel] = []
    deep_think          : bool = False


class QueryPageRequest(BaseModel):
    query_id  : str
    page      : int = 1
    page_size : int = 20
    sort_by   : str | None = None
    sort_dir  : str = "desc"


class SuggestionMoreRequest(BaseModel):
    token: str


class ChatResponse(BaseModel):
    session_id : str
    text       : str
    language   : str
    visualization : dict | None = None
    suggestions   : list[str] = []
    turn_number   : int
    conversation_id: str | None = None


class IntelligentChatResponse(BaseModel):
    session_id                  : str
    text                        : str
    language                    : str
    visualization               : dict | None = None
    orchestration_log           : list[dict] = []
    execution_duration_ms       : int = 0
    orchestration_duration_ms   : int = 0
    strategy_step_count         : int = 0
    tools_called                : list[str] = []
    suggestions                 : list[str] = []
    quality_pass_rate             : float = 1.0
    quality_checks_passed         : int = 0
    quality_checks_total          : int = 0
    quality_passed                : bool = True
    failure_mode                  : str | None = None
    cache_hit                     : bool = False
    proactive_cache_keys          : list[str] = []
    interaction_id                : str | None = None
    turn_number                   : int = 1


class LoginRequest(BaseModel):
    file_id: str


class LoginResponse(BaseModel):
    status          : str
    session_id      : str | None = None
    user_name       : str
    language        : str
    file_id         : str | None = None
    welcome_title   : str | None = None
    welcome_message : str | None = None
    audio_response  : str | None = None
    access_token    : str | None = None
    refresh_token   : str | None = None
    token_type      : str | None = None
    expires_in      : int | None = None
    roles           : list[str] | None = None
    permissions     : list[str] | None = None
    mfa_required    : bool | None = None
    mfa_token       : str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileResponse(BaseModel):
    user_name       : str
    language        : str
    file_id         : str | None = None
    welcome_title   : str | None = None
    welcome_message : str | None = None


class SessionRequest(BaseModel):
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status" : "ok",
        "version": "3.0.0",
        "model"  : "claude-sonnet-4-20250514",
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus scrape endpoint."""
    return StarletteResponse(
        content=metrics_payload(),
        media_type=metrics_content_type(),
    )


@app.get("/quality/metrics")
async def quality_metrics():
    total = QUALITY_METRICS["responses"] or 1
    return {
        **QUALITY_METRICS,
        "quality_pass_rate": round(QUALITY_METRICS["quality_pass"] / total, 4),
    }


@app.post("/auth/login", response_model=LoginResponse)
async def auth_login(request: LoginRequest, http_request: Request):
    try:
        return await login_with_file_id(request.file_id, request=http_request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[/auth/login] Unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail="Authentication failed") from exc


@app.post("/auth/refresh")
async def auth_refresh(request: RefreshRequest):
    return await refresh_tokens(request.refresh_token)


@app.post("/auth/logout")
async def auth_logout(request: SessionRequest):
    return await logout(request.session_id)


@app.get("/user/profile", response_model=ProfileResponse)
async def user_profile(
    http_request: Request,
    session_id: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    token = extract_bearer_token(http_request, credentials)
    if token:
        return await get_profile(token)
    return await get_profile(session_id)


def _iter_text_chunks(text: str, chunk_size: int = 64):
    """Yield fixed-size text slices for SSE streaming."""
    if not text:
        return
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def _tool_payloads_from_intelligent_result(
    result: IntelligentQueryResponse,
) -> tuple[list[str], list[Any]]:
    """Extract tool names and raw payloads from an orchestrated response."""
    tools_called = list(result.tools_called or [])
    tool_payloads: list[Any] = []
    execution = result.execution_result
    if execution is not None:
        for step_number in sorted(execution.results):
            tool_payloads.append(execution.results[step_number])
    return tools_called, tool_payloads


def _intelligent_progress_steps(language: str, *, deep_think: bool = False) -> list[dict[str, str]]:
    if deep_think:
        if language == "ar":
            return [
                {"label": "فهم السؤال", "status": "running"},
                {"label": "تفكير عميق — جلب البيانات من Odoo", "status": "pending"},
                {"label": "تحليل وإعداد الإجابة", "status": "pending"},
            ]
        return [
            {"label": "Understanding your question", "status": "running"},
            {"label": "Deep thinking — pulling data from Odoo", "status": "pending"},
            {"label": "Analyzing and preparing the answer", "status": "pending"},
        ]
    if language == "ar":
        return [
            {"label": "فهم السؤال", "status": "running"},
            {"label": "تحليل الطلب", "status": "pending"},
            {"label": "إعداد الإجابة", "status": "pending"},
        ]
    return [
        {"label": "Understanding your question", "status": "running"},
        {"label": "Analyzing your request", "status": "pending"},
        {"label": "Preparing response", "status": "pending"},
    ]


@app.post("/audit/stream")
async def audit_stream(
    request: ChatRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Audit/Analyze agent — separate from chat."""
    from gateway.audit.handler import AuditHandler

    chat_user = await require_chat_user(
        http_request, credentials, session_id=request.session_id
    )
    session_id = request.session_id or str(uuid4())

    async def generate():
        set_request_user(chat_user)
        stream_started = time.perf_counter()
        stream_status = "success"
        language = _detect_language(request.message)
        ai_streaming_connections.inc()
        try:
            try:
                adapter = get_adapter()
            except ConnectionError as exc:
                stream_status = "error"
                message = str(exc)
                yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'text': message, 'session_id': session_id})}\n\n"
                return

            handler = AuditHandler(adapter)
            async for chunk in handler.handle_stream(
                request.message,
                chat_user,
                session_id,
            ):
                yield chunk
        except Exception as exc:
            stream_status = "error"
            logger.error("[/audit/stream] Audit handler error: %s", exc)
            message = (
                "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى."
                if language == "ar"
                else "Sorry, I encountered an error. Please try again."
            )
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'text': message, 'session_id': session_id})}\n\n"
        finally:
            ai_streaming_connections.dec()
            chat_stream_duration.labels(status=stream_status).observe(
                time.perf_counter() - stream_started
            )
            record_ai_query(
                endpoint="/audit/stream",
                language=language,
                status=stream_status,
            )
            set_request_user(None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """
    Streaming chat endpoint.
    Returns text chunks as they are generated.
    Frontend renders text immediately.
    """
    from fastapi.responses import StreamingResponse as SR

    chat_user = await require_chat_user(
        http_request, credentials, session_id=request.session_id
    )
    session_id = request.session_id or str(uuid4())

    async def generate():
        set_request_user(chat_user)
        stream_started = time.perf_counter()
        stream_status = "success"
        language = _detect_language(request.message)
        ai_streaming_connections.inc()
        try:
            try:
                get_adapter()
            except ConnectionError as exc:
                stream_status = "error"
                message = str(exc)
                yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'text': message, 'session_id': session_id})}\n\n"
                return

            progress_steps = _intelligent_progress_steps(language, deep_think=request.deep_think)
            if request.deep_think:
                status_message = (
                    "تفكير عميق — جاري جلب البيانات..."
                    if language == "ar"
                    else "Deep thinking — pulling live data..."
                )
            else:
                status_message = (
                    "جاري تحليل السؤال..."
                    if language == "ar"
                    else "Analyzing your question..."
                )
            yield f"data: {json.dumps({'type': 'status', 'message': status_message})}\n\n"
            yield f"data: {json.dumps({'type': 'progress', 'steps': progress_steps})}\n\n"

            progress_steps[0]["status"] = "done"
            progress_steps[1]["status"] = "running"
            yield f"data: {json.dumps({'type': 'progress', 'steps': progress_steps})}\n\n"

            result = await _run_intelligent_chat(
                request.message,
                session_id,
                chat_user,
                skip_clarification=request.skip_clarification,
                confirmed_entities=_parse_confirmed_entities(request.confirmed_entities),
                deep_think=request.deep_think,
            )

            progress_steps[1]["status"] = "done"
            progress_steps[2]["status"] = "running"
            yield f"data: {json.dumps({'type': 'progress', 'steps': progress_steps})}\n\n"

            conv_id = ConversationStore.conversation_id_for_session(session_id)

            if result.awaiting_clarification and result.clarification:
                prompt = result.text or (
                    result.clarification.get("question_ar")
                    if language == "ar"
                    else result.clarification.get("question")
                ) or result.clarification.get("question", "")
                yield f"data: {json.dumps({'type': 'clarify', 'clarification': result.clarification})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'text': prompt, 'clarification': result.clarification, 'awaiting_clarification': True, 'session_id': session_id, 'conversation_id': conv_id, 'interaction_id': result.interaction_id})}\n\n"
                return

            tools_called, tool_payloads = _tool_payloads_from_intelligent_result(result)
            clean_text, visualization, suggestions, suggestion_meta = _finalize_agent_response(
                result.text,
                result.visualization,
                result.suggestions,
                tools_called,
                tool_payloads,
                language,
                request.message,
                session_id,
            )
            _log_agent_response(
                user_message=request.message,
                raw_text=result.text,
                clean_text=clean_text,
                visualization=visualization,
                suggestions=suggestions,
                tool_names=tools_called,
            )

            visual_type = (visualization or {}).get("visual_type")
            if visual_type:
                yield f"data: {json.dumps({'type': 'viz_hint', 'visual_type': visual_type})}\n\n"

            for chunk in _iter_text_chunks(clean_text):
                yield f"data: {json.dumps({'type': 'text', 'chunk': chunk})}\n\n"

            progress_steps[2]["status"] = "done"
            yield f"data: {json.dumps({'type': 'progress', 'steps': progress_steps})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'text': clean_text, 'visualization': visualization, 'suggestions': suggestions, 'suggestion_meta': suggestion_meta, 'session_id': session_id, 'conversation_id': conv_id, 'interaction_id': result.interaction_id, 'deep_think_available': result.deep_think_available})}\n\n"
        except Exception as exc:
            stream_status = "error"
            logger.error("[/chat/stream] Intelligent handler error: %s", exc)
            message = (
                "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى."
                if language == "ar"
                else "Sorry, I encountered an error. Please try again."
            )
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'text': message, 'session_id': session_id})}\n\n"
        finally:
            ai_streaming_connections.dec()
            chat_stream_duration.labels(status=stream_status).observe(
                time.perf_counter() - stream_started
            )
            record_ai_query(
                endpoint="/chat/stream",
                language=language,
                status=stream_status,
            )
            set_request_user(None)

    return SR(
        generate(),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control"              : "no-cache",
            "X-Accel-Buffering"          : "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    chat_user = await require_chat_user(
        http_request, credentials, session_id=request.session_id
    )
    session_id = request.session_id or str(uuid4())
    set_request_user(chat_user)
    try:
        result = await _run_intelligent_chat(
            request.message,
            session_id,
            chat_user,
            skip_clarification=request.skip_clarification,
            confirmed_entities=_parse_confirmed_entities(request.confirmed_entities),
            deep_think=request.deep_think,
        )
    except Exception as exc:
        logger.error("[/chat] Intelligent handler error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        set_request_user(None)

    user_id = chat_user.id if chat_user else None
    history = await ConversationStore.get(session_id, user_id=user_id)

    return ChatResponse(
        session_id=session_id,
        text=result.text,
        language=result.language,
        visualization=result.visualization,
        suggestions=result.suggestions,
        turn_number=len(history),
        conversation_id=ConversationStore.conversation_id_for_session(session_id),
    )


# Debug/canary path — returns full orchestration metadata for acceptance tests.
@app.post("/chat/intelligent", response_model=IntelligentChatResponse)
async def chat_intelligent(
    request: ChatRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    chat_user = await require_chat_user(
        http_request, credentials, session_id=request.session_id
    )
    session_id = request.session_id or str(uuid4())
    set_request_user(chat_user)
    try:
        result = await _run_intelligent_chat(
            request.message,
            session_id,
            chat_user,
            skip_clarification=request.skip_clarification,
            confirmed_entities=_parse_confirmed_entities(request.confirmed_entities),
            deep_think=request.deep_think,
        )
    except Exception as exc:
        logger.error("[/chat/intelligent] Orchestration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        set_request_user(None)

    user_id = chat_user.id if chat_user else None
    history = await ConversationStore.get(session_id, user_id=user_id)

    return IntelligentChatResponse(
        session_id=session_id,
        text=result.text,
        language=result.language,
        visualization=result.visualization,
        orchestration_log=result.orchestration_log,
        execution_duration_ms=result.execution_duration_ms,
        orchestration_duration_ms=result.orchestration_duration_ms,
        strategy_step_count=result.strategy_step_count,
        tools_called=result.tools_called,
        suggestions=result.suggestions,
        quality_pass_rate=result.quality_pass_rate,
        quality_checks_passed=result.quality_checks_passed,
        quality_checks_total=result.quality_checks_total,
        quality_passed=result.quality_passed,
        failure_mode=result.failure_mode,
        cache_hit=result.cache_hit,
        proactive_cache_keys=result.proactive_cache_keys,
        interaction_id=result.interaction_id,
        turn_number=len(history),
    )


@app.post("/suggestions/more")
async def suggestions_more(
    request: SuggestionMoreRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Return the next batch of post-response suggestions (Phase 6)."""
    await require_chat_user(http_request, credentials)
    from gateway.suggestion_pool import rotate_post_response_suggestions

    suggestions, has_more = rotate_post_response_suggestions(request.token)
    if not suggestions:
        raise HTTPException(
            status_code=400,
            detail="Suggestion session expired. Please run the report again.",
        )
    return {
        "suggestions": suggestions,
        "suggestion_meta": {
            "token": request.token,
            "has_more": has_more,
        },
    }


class DeepThinkEligibilityRequest(BaseModel):
    message: str


@app.post("/deep-think/eligibility")
async def deep_think_eligibility(
    request: DeepThinkEligibilityRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Cheap keyword-based check whether Deep Think applies to the typed query."""
    await require_chat_user(http_request, credentials)
    from gateway.core.deep_think import is_deep_think_eligible

    return {"eligible": is_deep_think_eligible(request.message)}


@app.post("/query/page")
async def query_page(
    request: QueryPageRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Return a paginated slice of a cached tabular query (Phase 4)."""
    await require_chat_user(http_request, credentials)
    from gateway.query_pagination import QueryPageStore

    try:
        return QueryPageStore.get_page(
            request.query_id,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_dir=request.sort_dir,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail="Query expired or not found. Please run the report again.",
        ) from exc


@app.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Clear conversation history for a session."""
    chat_user = await require_chat_user(
        http_request, credentials, session_id=session_id
    )
    await ConversationStore.clear(
        session_id,
        user_id=chat_user.id if chat_user else None,
    )
    from gateway.session_scope import SessionScopeStore

    SessionScopeStore.clear(session_id)
    conv_id = ConversationStore.conversation_id_for_session(session_id)
    return {
        "status": "cleared",
        "session_id": session_id,
        "conversation_id": conv_id,
    }


@app.post("/voice")
async def voice(
    http_request: Request,
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """
    Voice conversation endpoint.

    Accepts : audio file (wav, mp3, m4a, webm, ogg)
    Returns : audio/mpeg stream (spoken response)

    Pipeline:
        Audio upload → Whisper STT → Claude Agent → ElevenLabs TTS → Audio
    """
    chat_user = await require_chat_user(
        http_request, credentials, session_id=session_id
    )
    session_id = session_id or str(uuid4())
    set_request_user(chat_user)
    try:
        return await _voice_pipeline(
            audio=audio,
            session_id=session_id,
            chat_user=chat_user,
            user_id=chat_user.id if chat_user else None,
            extension_from_filename=audio.filename or "audio.webm",
        )
    finally:
        set_request_user(None)


async def _voice_pipeline(
    *,
    audio: UploadFile,
    session_id: str,
    chat_user: CurrentUser,
    user_id: int | None = None,
    extension_from_filename: str,
) -> StreamingResponse:
    filename  = extension_from_filename
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"

    # Save uploaded audio to temp file
    try:
        content = await audio.read()
        if len(content) < 1024:
            raise HTTPException(
                status_code=422,
                detail="Audio recording is too short. Hold the microphone a little longer and try again.",
            )

        suffix = f".{extension}" if extension else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to save audio: {exc}"
        )

    try:
        # Step 1: STT — transcribe audio to text
        stt = get_stt()
        try:
            transcript = stt.transcribe(tmp_path)
            logger.info("[/voice] Transcript: '%s'", transcript)
        except Exception as exc:
            logger.exception("[/voice] Transcription failed")
            raise HTTPException(
                status_code=422,
                detail=f"Speech transcription failed: {exc}"
            )

        if not transcript.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not transcribe audio. Please speak clearly and try again."
            )

        if user_id:
            minutes = max(0.1, len(content) / 48000.0)
            schedule_usage(track_voice_minutes(user_id, minutes))

        # Step 2: Run intelligent handler (same entity gate as text chat)
        try:
            result = await _run_intelligent_chat(
                transcript,
                session_id,
                chat_user,
            )
            response = {
                "text": result.text,
                "language": result.language,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        text     = response.get("text", "I could not process your request.")
        language = response.get("language", "en")

        # Step 3: TTS — convert response to speech
        tts = get_tts()
        try:
            audio_bytes = tts.synthesize(text, language=language)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Speech synthesis failed: {exc}"
            )

        # Return audio stream with metadata headers
        return StreamingResponse(
            iter([audio_bytes]),
            media_type = "audio/mpeg",
            headers    = {
                "X-Session-Id"     : session_id,
                "X-Language"       : language,
                "X-Transcript"     : _ascii_header(transcript),
                "X-Response"       : _ascii_header(text),
                "X-Transcript-B64" : _utf8_header(transcript),
                "X-Response-B64"   : _utf8_header(text),
            },
        )

    finally:
        # Clean up temp file
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Static UI (ooa-ui/build) — register last so API routes take precedence
# ---------------------------------------------------------------------------

_UI_BUILD_DIR = Path(__file__).resolve().parent.parent / "ooa-ui" / "build"


def _register_frontend() -> None:
    index = _UI_BUILD_DIR / "index.html"
    if not index.is_file():
        logger.warning(
            "UI build not found at %s — run: cd ooa-ui && npm run build",
            _UI_BUILD_DIR,
        )

        @app.get("/", include_in_schema=False)
        async def root_info() -> dict[str, str]:
            return {
                "service": "OOA Gateway",
                "version": "3.0.0",
                "health": "/health",
                "metrics": "/metrics",
                "hint": "cd ooa-ui && npm run build, then restart the gateway",
            }

        return

    static_dir = _UI_BUILD_DIR / "static"
    if static_dir.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="ooa-ui-static",
        )

    @app.get("/", include_in_schema=False)
    async def serve_ui_root() -> FileResponse:
        return FileResponse(index)

    @app.get("/{ui_path:path}", include_in_schema=False)
    async def serve_ui_asset(ui_path: str) -> FileResponse:
        """Serve built assets; SPA paths fall back to index.html."""
        if ui_path.startswith(
            ("auth/", "chat/", "admin/", "user/", "voice/", "reports/", "quality/")
        ):
            raise HTTPException(status_code=404, detail="Not found")
        if ui_path in ("health", "metrics"):
            raise HTTPException(status_code=404, detail="Not found")
        asset = (_UI_BUILD_DIR / ui_path).resolve()
        if not str(asset).startswith(str(_UI_BUILD_DIR.resolve())):
            raise HTTPException(status_code=404, detail="Not found")
        if asset.is_file():
            return FileResponse(asset)
        return FileResponse(index)


_register_frontend()