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

import json
import logging
import os
from datetime import datetime
from typing import Any
from uuid import uuid4

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import tempfile
from integrations.voice_engine import WhisperSTT, ElevenLabsTTS

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from adapters.v14.connector import OdooV14Adapter
from core.base_adapter import OdooConnectionConfig
from core.state import OdooVersion

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title   = "Odoo Omni-Agent",
    version = "3.0.0",
    docs_url= "/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)
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
# ---------------------------------------------------------------------------
# In-memory conversation store
# ---------------------------------------------------------------------------

class ConversationStore:
    """
    Stores conversation history per session.
    Uses PostgreSQL if POSTGRES_DSN is set, otherwise in-memory.
    """
    _memory: dict[str, list] = {}
    _use_postgres = bool(os.environ.get("POSTGRES_DSN"))

    @classmethod
    def _ensure_table(cls, conn) -> None:
        import psycopg2
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ooa_conversations (
                    session_id  TEXT PRIMARY KEY,
                    messages    JSONB NOT NULL DEFAULT '[]',
                    updated_at  TIMESTAMPTZ DEFAULT now()
                )
            """)
        conn.commit()

    @classmethod
    def _get_pg_connection(cls):
        import psycopg2
        conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
        cls._ensure_table(conn)
        return conn

    @classmethod
    def get(cls, session_id: str) -> list:
        if cls._use_postgres:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT messages FROM ooa_conversations WHERE session_id = %s",
                        (session_id,)
                    )
                    row = cur.fetchone()
                conn.close()
                return row[0] if row else []
            except Exception as exc:
                logger.error("[ConversationStore] PG get failed: %s", exc)
                return cls._memory.get(session_id, [])
        return cls._memory.get(session_id, [])

    @classmethod
    def save(cls, session_id: str, messages: list) -> None:
        if cls._use_postgres:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ooa_conversations (session_id, messages, updated_at)
                        VALUES (%s, %s::jsonb, now())
                        ON CONFLICT (session_id) DO UPDATE
                        SET messages = EXCLUDED.messages, updated_at = now()
                    """, (session_id, json.dumps(messages, default=str)))
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.error("[ConversationStore] PG save failed: %s", exc)
                cls._memory[session_id] = messages
        else:
            cls._memory[session_id] = messages

    @classmethod
    def append(cls, session_id: str, role: str, content: Any) -> None:
        messages = cls.get(session_id)
        messages.append({"role": role, "content": content})
        if len(messages) > 20:
            messages = messages[-20:]
        cls.save(session_id, messages)

    @classmethod
    def clear(cls, session_id: str) -> None:
        if cls._use_postgres:
            try:
                conn = cls._get_pg_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM ooa_conversations WHERE session_id = %s",
                        (session_id,)
                    )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.error("[ConversationStore] PG clear failed: %s", exc)
        cls._memory.pop(session_id, None)

    # @classmethod
    # def get(cls, session_id: str) -> list:
    #     return cls._store.get(session_id, [])

    # @classmethod
    # def append(cls, session_id: str, role: str, content: Any) -> None:
    #     if session_id not in cls._store:
    #         cls._store[session_id] = []
    #     cls._store[session_id].append({
    #         "role"   : role,
    #         "content": content,
    #     })
    #     # Keep last 20 turns
    #     if len(cls._store[session_id]) > 20:
    #         cls._store[session_id] = cls._store[session_id][-20:]

    # @classmethod
    # def clear(cls, session_id: str) -> None:
    #     cls._store.pop(session_id, None)


# ---------------------------------------------------------------------------
# Odoo Adapter Factory
# ---------------------------------------------------------------------------

# Cached adapter — authenticate once, reuse connection
_adapter: OdooV14Adapter | None = None

def get_adapter() -> OdooV14Adapter:
    global _adapter
    if _adapter is None:
        config = OdooConnectionConfig(
            url      = os.environ["ODOO_V14_URL"],
            database = os.environ["ODOO_V14_DB"],
            username = os.environ["ODOO_V14_USER"],
            api_key  = os.environ["ODOO_V14_PASSWORD"],
            version  = OdooVersion.V14,
        )
        _adapter = OdooV14Adapter(config)
        _adapter.authenticate()
        logger.info("[Adapter] Connected to Odoo — uid: %d", _adapter._uid)
    return _adapter

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
            "Get financial data for a SPECIFIC project: total cost, expense breakdown, "
            "budget status, weekly trend, cost distribution (LPO, Petty Cash, Labor, Staff). "
            "Use this when user mentions a specific project name."
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
            "Get detailed P&L financial data for a SPECIFIC project with date range. "
            "Returns income, expense, net profit, margin for the project."
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
            "Get a summary list of all active projects with their financial data. "
            "Use when user asks for ALL projects breakdown, project list with costs, "
            "or wants to compare multiple projects."
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
        "name"       : "search_odoo",
        "description": (
            "Search any Odoo model for records. Use for: projects, invoices, "
            "employees, customers, purchase orders, etc. "
            "Returns a list of matching records."
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
                    "description": "Max records to return. Default 10.",
                },
                "order": {
                    "type"       : "string",
                    "description": "Sort order e.g. 'date desc'",
                },
            },
            "required": ["model", "fields"],
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
) -> Any:
    """Executes a tool call and returns the result."""
    logger.info("[Tool] %s(%s)", tool_name, tool_input)

    try:
        if tool_name == "get_financial_report":
            return adapter.accounting.get_financial_report(
                report_type = tool_input.get("report_type", "pandl"),
                date_from   = tool_input.get("date_from"),
                date_to     = tool_input.get("date_to"),
            )
        if tool_name == "get_trial_balance":
            return adapter.call_method(
                "project.financial.service",
                "get_ai_trial_balance",
                [tool_input.get("date_from"), tool_input.get("date_to")],
            )
        if tool_name == "get_projects_summary":
            limit = tool_input.get("limit", 20)
            projects = adapter.search_read(
                model  = "project.project",
                domain = [["active", "=", True]],
                fields = ["id", "name", "partner_id", "user_id",
                        "wo_ref_no", "date_start", "date"],
                limit  = limit,
                order  = "name asc",
            )
            return {
                "projects"     : projects,
                "total_count"  : len(projects),
                "note"         : "For financial data per project, use get_project_expenses with project name",
            }
        if tool_name == "get_partner_ageing":
            return adapter.call_method(
                "project.financial.service",
                "get_ai_partner_ageing",
                [
                    tool_input.get("date_from"),
                    tool_input.get("result_selection", "customer"),
                ],
            )

        if tool_name == "get_partner_ledger":
            return adapter.call_method(
                "project.financial.service",
                "get_ai_partner_ledger",
                [
                    tool_input.get("date_from"),
                    tool_input.get("date_to"),
                    tool_input.get("result_selection", "customer_supplier"),
                ],
            )
        if tool_name == "get_project_expenses":
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
                return response.raw_data
            except ProjectAmbiguousError as exc:
                # Return candidates so Claude can ask user to pick
                candidates = []
                for c in exc.candidates:
                    candidates.append({
                        "id"       : c.get("id"),
                        "name"     : c.get("name"),
                        "wo_ref_no": c.get("wo_ref_no"),
                        "client"   : c.get("partner_id")[1] if isinstance(c.get("partner_id"), list) else c.get("partner_id"),
                    })
                return {
                    "error"     : "multiple_projects_found",
                    "message"   : f"Found {len(candidates)} projects matching your search.",
                    "candidates": candidates,
                }
            except ProjectNotFoundError as exc:
                return {
                    "error"  : "project_not_found",
                    "message": f"No project found matching '{exc.search_term}'. Please provide the WO reference number or full project name.",
                }

        if tool_name == "get_project_financial_data":
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
                return response.raw_data
            except ProjectAmbiguousError as exc:
                candidates = []
                for c in exc.candidates:
                    candidates.append({
                        "id"       : c.get("id"),
                        "name"     : c.get("name"),
                        "wo_ref_no": c.get("wo_ref_no"),
                        "client"   : c.get("partner_id")[1] if isinstance(c.get("partner_id"), list) else c.get("partner_id"),
                    })
                return {
                    "error"     : "multiple_projects_found",
                    "message"   : f"Found {len(candidates)} projects matching your search.",
                    "candidates": candidates,
                }
            except ProjectNotFoundError as exc:
                return {
                    "error"  : "project_not_found",
                    "message": f"No project found matching '{exc.search_term}'. Please provide the WO reference number or full project name.",
                }

        if tool_name == "get_general_ledger":
            return adapter.accounting.get_general_ledger(
                date_from = tool_input.get("date_from"),
                date_to   = tool_input.get("date_to"),
            )

        if tool_name == "get_trial_balance":
            return adapter.accounting.get_trial_balance(
                date_from = tool_input.get("date_from"),
                date_to   = tool_input.get("date_to"),
            )

        if tool_name == "get_partner_ageing":
            return adapter.accounting.get_partner_ageing(
                date_from        = tool_input.get("date_from"),
                result_selection = tool_input.get("result_selection", "customer"),
            )

        if tool_name == "search_odoo":
            return adapter.search_read(
                model  = tool_input["model"],
                domain = tool_input.get("filters", []),
                fields = tool_input["fields"],
                limit  = tool_input.get("limit", 10),
                order  = tool_input.get("order"),
            )

        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.error("[Tool] %s failed: %s", tool_name, exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Claude Agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an intelligent ERP assistant for an Odoo system used by a 
Construction & Facilities Management company in UAE (Elrace).

Today's date: {today}

You have access to Odoo tools to fetch real data. Use them when needed.

Guidelines:
- Respond in the SAME language the user writes in (Arabic, English, or Urdu)
- Be concise and direct — answer what was asked, not the full report
- Format numbers with commas and include AED currency
- For financial reports: summarize key figures, don't dump all lines
- For project data: highlight total cost, budget status, key expenses
- If data has many items: show top 5-10 and mention total count
- You can answer general questions (date, greetings, capabilities) directly
- For financial reports without a date: always ask which period before fetching
- For project queries without a project name: always ask which project
- Always be helpful, professional, and accurate

Company context:
- Based in UAE, operates in Abu Dhabi and Dubai
- Construction, facilities management, maintenance projects
- Multiple projects with Arabic and English names
- Currency: AED
IMPORTANT — STRUCTURED OUTPUT:
After your natural language response, if you fetched any data, you MUST append 
a visualization block in this exact format (no spaces before <visualization>):

<visualization>
{
  "visual_type": "KPI_CARD|BAR_CHART|LINE_CHART|DATA_TABLE|FINANCIAL_REPORT",
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
- P&L / Balance Sheet hierarchy → FINANCIAL_REPORT

For suggestions: provide 3 natural follow-up questions the user might ask next,
in the SAME language as the response.

If no data was fetched (greetings, general questions), omit the visualization block."""


async def run_agent(
    user_message: str,
    session_id  : str,
) -> dict[str, Any]:
    """
    Runs the Claude agent with tool use.
    Claude decides what tools to call and how to respond.
    """
    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    adapter = get_adapter()
    today   = datetime.now().strftime("%A, %d %B %Y")

    # Get conversation history
    history = ConversationStore.get(session_id)

    # Add user message to history
    ConversationStore.append(session_id, "user", user_message)
    messages = ConversationStore.get(session_id)

    logger.info(
        "[Agent] session=%s | turn=%d | input='%s'",
        session_id, len(messages), user_message[:60],
    )

    # Agentic loop — Claude may call multiple tools
    while True:
        response = client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 4096,
            system     = SYSTEM_PROMPT.replace("{today}", today),
            tools      = TOOLS,
            messages   = messages,
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

            # Parse visualization block if present
            visualization = None
            suggestions   = []

            if "<visualization>" in text and "</visualization>" in text:
                try:
                    viz_start = text.index("<visualization>") + len("<visualization>")
                    viz_end   = text.index("</visualization>")
                    viz_json  = text[viz_start:viz_end].strip()

                    # Strip markdown fences if Claude wrapped it
                    if viz_json.startswith("```"):
                        lines     = viz_json.split("\n")
                        viz_json  = "\n".join(
                            l for l in lines
                            if not l.strip().startswith("```")
                        )

                    viz_data      = json.loads(viz_json)
                    suggestions   = viz_data.pop("suggestions", [])
                    visualization = viz_data

                    # Remove the visualization block from text
                    text = text[:text.index("<visualization>")].strip()

                except json.JSONDecodeError as exc:
                    logger.warning(
                        "[Agent] Visualization JSON parse failed: %s | raw: %s",
                        exc,
                        viz_json[:200] if 'viz_json' in dir() else "N/A",
                    )
                except Exception as exc:
                    logger.warning("[Agent] Visualization parse error: %s", exc)

            # Save assistant response to history
            ConversationStore.append(session_id, "assistant", text)

            return {
                "text"         : text,
                "language"     : _detect_language(user_message),
                "visualization": visualization,
                "suggestions"  : suggestions,
                "turn_number"  : len(ConversationStore.get(session_id)),
            }

        # Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Add Claude's response to messages
            messages.append({
                "role"   : "assistant",
                "content": response.content,
            })

            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(
                        "[Agent] Tool call: %s(%s)",
                        block.name,
                        json.dumps(block.input, default=str)[:100],
                    )

                    import asyncio
                    result = await asyncio.to_thread(execute_tool, block.name, block.input, adapter)

                    # Truncate large results to avoid token overflow
                    result_str = json.dumps(result, default=str)
                    if len(result_str) > 50000:
                        # For large reports keep only summary
                        if isinstance(result, dict):
                            result = _summarize_large_result(result)
                        result_str = json.dumps(result, default=str)

                    tool_results.append({
                        "type"       : "tool_result",
                        "tool_use_id": block.id,
                        "content"    : result_str,
                    })

            # Add tool results to messages
            messages.append({
                "role"   : "user",
                "content": tool_results,
            })

            # Update conversation store
            # ConversationStore.save(session_id, messages)
            continue

        # Unexpected stop reason
        break

    return {
        "text"        : "I encountered an issue processing your request.",
        "language"    : "en",
        "visualization": None,
        "suggestions" : [],
        "turn_number" : 1,
    }


def _summarize_large_result(data: dict) -> dict:
    """Truncates large Odoo responses to prevent token overflow."""
    summary = {}
    for key, value in data.items():
        if key == "report_lines" and isinstance(value, list):
            # Keep only top-level lines (level 0,1,2)
            summary[key] = [
                l for l in value
                if l.get("level", 0) <= 2
            ][:20]
        elif key == "accounts" and isinstance(value, dict):
            # Keep first 30 accounts summary only
            items = list(value.items())[:30]
            summary[key] = {
                k: {
                    "name"   : v.get("name"),
                    "debit"  : v.get("debit"),
                    "credit" : v.get("credit"),
                    "balance": v.get("balance"),
                }
                for k, v in items
            }
        elif key == "distribution" and isinstance(value, list):
            summary[key] = value
        elif key in ("kpis", "totals", "filters",
                     "report_name", "date_from", "date_to",
                     "project_name", "exceed_percent",
                     "commitment_total", "cost_totals"):
            summary[key] = value
        else:
            summary[key] = value
    return summary


def _detect_language(text: str) -> str:
    """Simple language detection based on script."""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    if arabic_chars > len(text) * 0.3:
        return "ar"
    return "en"


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message    : str
    session_id : str | None = None


class ChatResponse(BaseModel):
    session_id : str
    text       : str
    language   : str
    visualization : dict | None = None
    suggestions   : list[str] = []
    turn_number   : int


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

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint.
    Returns text chunks as they are generated.
    Frontend renders text immediately.
    """
    from fastapi.responses import StreamingResponse as SR
    import asyncio

    session_id = request.session_id or str(uuid4())

    async def generate():
        client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        adapter = get_adapter()
        today   = datetime.now().strftime("%A, %d %B %Y")

        ConversationStore.append(session_id, "user", request.message)
        messages = ConversationStore.get(session_id)

        full_text = ""

        # Agentic loop
        while True:
            # Use streaming
            with client.messages.stream(
                model      = "claude-sonnet-4-20250514",
                max_tokens = 2048,
                system     = SYSTEM_PROMPT.replace("{today}", today),
                tools      = TOOLS,
                messages   = messages,
            ) as stream:
                tool_calls_made = False

                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                chunk = event.delta.text
                                full_text += chunk
                                # Stream text chunk to client
                                yield f"data: {json.dumps({'type': 'text', 'chunk': chunk})}\n\n"

                final_message = stream.get_final_message()

                if final_message.stop_reason == "tool_use":
                    tool_calls_made = True
                    messages.append({
                        "role"   : "assistant",
                        "content": final_message.content,
                    })

                    tool_results = []
                    for block in final_message.content:
                        if block.type == "tool_use":
                            yield f"data: {json.dumps({'type': 'tool', 'name': block.name})}\n\n"
                            result = await asyncio.to_thread(
                                execute_tool, block.name, block.input, adapter
                            )
                            result_str = json.dumps(result, default=str)
                            if len(result_str) > 50000:
                                if isinstance(result, dict):
                                    result = _summarize_large_result(result)
                                result_str = json.dumps(result, default=str)

                            tool_results.append({
                                "type"       : "tool_result",
                                "tool_use_id": block.id,
                                "content"    : result_str,
                            })

                    messages.append({
                        "role"   : "user",
                        "content": tool_results,
                    })
                    full_text = ""  # Reset for next response
                    continue

                break

        # Parse visualization from full text
        visualization = None
        suggestions   = []
        clean_text    = full_text

        if "<visualization>" in full_text and "</visualization>" in full_text:
            try:
                viz_start  = full_text.index("<visualization>") + len("<visualization>")
                viz_end    = full_text.index("</visualization>")
                viz_json   = full_text[viz_start:viz_end].strip()
                viz_data   = json.loads(viz_json)
                suggestions   = viz_data.pop("suggestions", [])
                visualization = viz_data
                clean_text    = full_text[:full_text.index("<visualization>")].strip()
            except Exception:
                pass

        ConversationStore.append(session_id, "assistant", clean_text)

        # Send final metadata
        yield f"data: {json.dumps({'type': 'done', 'visualization': visualization, 'suggestions': suggestions, 'session_id': session_id})}\n\n"

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
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    try:
        response = await run_agent(request.message, session_id)
    except Exception as exc:
        logger.error("[/chat] Agent error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(
        session_id    = session_id,
        text          = response.get("text", ""),
        language      = response.get("language", "en"),
        visualization = response.get("visualization"),
        suggestions   = response.get("suggestions", []),
        turn_number   = response.get("turn_number", 1),
    )


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    ConversationStore.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.post("/voice")
async def voice(audio: UploadFile = File(...)):
    """
    Voice conversation endpoint.

    Accepts : audio file (wav, mp3, m4a, webm, ogg)
    Returns : audio/mpeg stream (spoken response)

    Pipeline:
        Audio upload → Whisper STT → Claude Agent → ElevenLabs TTS → Audio
    """
    session_id = str(uuid4())

    # Validate file type
    allowed_types = {
        "audio/wav", "audio/wave", "audio/mpeg",
        "audio/mp3", "audio/mp4", "audio/m4a",
        "audio/webm", "audio/ogg", "audio/x-m4a",
    }
    content_type = audio.content_type or ""
    filename     = audio.filename or "audio.wav"
    extension    = filename.split(".")[-1].lower()

    # Save uploaded audio to temp file
    try:
        suffix = f".{extension}" if extension else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content  = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name
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
            raise HTTPException(
                status_code=422,
                detail=f"Speech transcription failed: {exc}"
            )

        if not transcript.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not transcribe audio. Please speak clearly and try again."
            )

        # Step 2: Run Claude agent
        try:
            response = run_agent(transcript, session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

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
                "X-Session-Id" : session_id,
                "X-Language"   : language,
            },
        )

    finally:
        # Clean up temp file
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass