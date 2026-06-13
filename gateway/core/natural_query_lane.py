"""Natural Query Fast Lane — agentic fallback when the pipeline cannot classify a query.

When the intent analyzer signals uncertainty (subject_area='other' or ambiguous
cross-entity phrasing like "Adil Khan vehicle"), bypass the rigid pipeline and
let Claude reason directly with all tools available.

CONTINUATION DESIGN:
  When the fast lane asks "which Adil Khan?", the user's reply must go back to
  the fast lane — NOT the entity gate. We persist fast_lane_pending in the session
  and check it as Signal 0 in should_use_fast_lane().

  For continuation turns we do NOT reconstruct the messy formatted history.
  Instead we merge the original query + the user's selection into a single clean
  message: "Adil khan vehicle — user selected: Adil Khan Sher Dil Khan (ID 698)".
  This avoids confusing Claude with long markdown assistant turns.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import anthropic

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent
from gateway.tools.universal_odoo import UNIVERSAL_ODOO_TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

FAST_LANE_MODEL = "claude-sonnet-4-20250514"
FAST_LANE_MAX_TURNS = 5
FAST_LANE_MAX_TOKENS = 2048
TOOL_RESULT_CHAR_LIMIT = 10000

FAST_LANE_SESSION_KEY = "fast_lane_pending"

# Financial query phrases — these must NEVER hit the fast lane even if the intent
# analyzer says subject_area='other' (it doesn't recognise abbreviations like "pnl").
# The normal pipeline handles them via get_financial_report.
_FINANCIAL_EXCLUDES: tuple[str, ...] = (
    "pnl", "p&l", "profit", "loss", "balance sheet", "pandl",
    "cash flow", "revenue", "income statement",
)

# Cross-entity signals: words suggesting the query spans multiple Odoo models.
_CROSS_ENTITY_SIGNALS: frozenset[str] = frozenset(
    {
        "vehicle", "vehicles", "car", "cars",
        "attendance", "attendances",
        "visa", "visas", "passport", "passports",
        "insurance", "renewal",
        "allocation", "allocations",
    }
)

FAST_LANE_SYSTEM_PROMPT = """\
You are the Elrace ERP assistant. The query you received could not be confidently
classified by the rigid intent pipeline. You have FULL POWER to answer it using tools.

YOUR TOOLS:
  query_odoo              — read any Odoo model (hr.employee, fleet.vehicle, hr.payslip, ...)
  aggregate_odoo          — count/sum/avg with grouping
  introspect_odoo_schema  — discover models and fields when unsure

KEY ELRACE MODELS:
  Employees    : hr.employee (fields: name, job_title, department_id, file_id, visa_expire,
                   passport_expiry_date, labour_card_expiry_date, project_id_store, branch_id)
  Vehicles     : fleet.vehicle (fields: name, license_plate, model_id, employee_id, driver_id,
                   state_id, insurance_expiry_date, next_assignation_date)
  Payslips     : hr.payslip (fields: name, employee_id, date_from, date_to, net_wage,
                   fine, advance, total_deductions, pension, unemployment_insurance)
  Attendance   : hr.attendance (fields: employee_id, check_in, check_out)
  Requests     : employee.request (fields: employee_id, request_type, state, date_start, date_end)
  Projects     : project.project (fields: name, partner_id, contract_amount)
  Partners     : res.partner
  Departments  : hr.department

HOW TO ANSWER:
1. Read the query carefully. Handle typos and natural phrasing (Arabic/Urdu mixed in).
2. Identify entities (person names, project names, date hints) and what is being asked about them.
3. For cross-entity queries ("Adil Khan vehicle"):
   - Step 1: query_odoo hr.employee to find the employee.
   - If ONE match: immediately proceed to step 2 (look up vehicle/attendance/etc).
   - If MULTIPLE matches: list names + IDs and ask which one. Stop there — do NOT proceed.
4. When the user confirms an employee by name or ID, go DIRECTLY to the related record.
   Do NOT re-search employees. Use the ID provided and query the target model.
5. Use introspect_odoo_schema when unsure of field names.
6. If no data found, explain and ask for more detail.

IMPORTANT — VEHICLE LOOKUP PATTERN:
  After confirming employee_id, ALWAYS use this domain:
    ["|", ["employee_id","=", <id>], ["driver_id","=", <id>]]
  If that returns nothing, try:
    [["employee_id.name","ilike","<name>"]]

IMPORTANT — DO NOT:
  - Re-search all employees when the user has already given you an ID.
  - Call query_odoo with an empty domain [] — always filter.
  - Ask about financial data when looking up vehicles/attendance/etc.

EXAMPLES:

Fresh query — "Adil Khan vehicle":
  1. query_odoo("hr.employee", [["name","ilike","Adil Khan"]], ["id","name","file_id"], limit=5)
  2a. One result → query_odoo("fleet.vehicle", ["|",["employee_id","=",id],["driver_id","=",id]],
        ["name","license_plate","model_id","state_id"])
  2b. Multiple → list them and ask which one (STOP, wait for reply).

Continuation — "Adil khan vehicle — user selected: Adil Khan Sher Dil Khan (employee id=698)":
  → Go DIRECTLY to fleet.vehicle:
    query_odoo("fleet.vehicle", ["|",["employee_id","=",698],["driver_id","=",698]],
               ["name","license_plate","model_id","state_id","employee_id"])
  → Report the vehicle. No need to re-search employees.

PERMISSIONS:
  - Read-only. Never call create/write/unlink.
  - System models (res.users, ir.config_parameter) are forbidden.

RESPOND IN THE USER'S LANGUAGE. Be concise. Use tables or lists when helpful.
Today's date: {today}
{session_context}
"""


def should_use_fast_lane(
    intent: Intent,
    message: str,
    context: ContextStack | None = None,
) -> bool:
    """Decide whether to bypass the pipeline for this query.

    Signal 0 — active fast-lane follow-up (highest priority, checked first).
    Signal 1 — intent classifier uncertainty (subject_area='other').
    Signal 2 — 'general' subject with cross-entity keywords.

    Financial queries are explicitly excluded even if subject_area='other'
    because the normal pipeline handles them via get_financial_report.
    """
    # Signal 0: active fast-lane follow-up — the user is replying to the
    # fast lane's disambiguation question. Must route back here, not to entity gate.
    if context is not None:
        pending = context.working_memory.session_facts.get(FAST_LANE_SESSION_KEY)
        if isinstance(pending, dict) and pending.get("awaiting_clarification"):
            logger.debug("[FastLane] Signal 0 — follow-up pending=%r", pending.get("original_query"))
            return True

    # Financial queries must never hit the fast lane — the normal pipeline handles
    # them correctly via get_financial_report. The intent analyzer sometimes returns
    # subject_area='other' for abbreviations like "pnl" but the pipeline recovers.
    msg_lower = message.lower()
    if any(phrase in msg_lower for phrase in _FINANCIAL_EXCLUDES):
        return False

    # Signal 1: intent classifier expressed uncertainty
    if intent.subject_area == "other":
        return True

    # Signal 2: 'general' subject with cross-entity keywords
    if intent.subject_area == "general":
        words = {w.lower().rstrip("s") for w in message.split()}
        if words & {w.rstrip("s") for w in _CROSS_ENTITY_SIGNALS}:
            return True

    return False


def _response_is_question(text: str) -> bool:
    """True when Claude's response ends with a question (disambiguation still pending)."""
    stripped = text.rstrip()
    return stripped.endswith("?") or "?" in stripped[-150:]


class NaturalQueryLane:
    """Bypass-pipeline agentic handler — Claude reasons directly with tools."""

    def __init__(
        self,
        *,
        adapter: Any,
        session_id: str | None = None,
        user: Any | None = None,
    ) -> None:
        self._adapter = adapter
        self._session_id = session_id
        self._user = user
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=os.environ["ANTHROPIC_API_KEY"]
            )
        return self._client

    def _build_system_prompt(self, context: ContextStack, is_continuation: bool) -> str:
        from datetime import date

        today = date.today().isoformat()
        session_context_lines: list[str] = []

        if is_continuation:
            # When continuing a fast-lane flow, do NOT inject payroll/payslip context
            # from previous unrelated queries — it contaminates the lookup.
            session_context_lines.append(
                "NOTE: Complete the task as stated in the user's message. "
                "Use the employee ID/name already provided — do NOT re-search employees. "
                "Go directly to the target model (fleet.vehicle, hr.attendance, etc.)."
            )
        else:
            sf = context.working_memory.session_facts
            if sf.get("pending_hr_context"):
                session_context_lines.append(
                    f"Session HR context: {json.dumps(sf['pending_hr_context'], default=str)}"
                )
            if sf.get("last_payslip_scope"):
                session_context_lines.append(
                    f"Last payslip scope: {json.dumps(sf['last_payslip_scope'], default=str)}"
                )
            active = context.working_memory.get_active_project()
            if active and active.project_id:
                session_context_lines.append(
                    f"Active project: {active.project_name} (id={active.project_id})"
                )

        session_context = "\n".join(session_context_lines)
        return FAST_LANE_SYSTEM_PROMPT.format(today=today, session_context=session_context)

    def _build_messages(
        self,
        message: str,
        context: ContextStack,
    ) -> list[dict[str, Any]]:
        """Build messages for the API call.

        For continuation turns: merge original query + user selection into one
        clean synthetic message instead of reconstructing the long formatted history.
        Long formatted assistant turns confuse Claude into re-querying everything.
        """
        sf = context.working_memory.session_facts
        pending = sf.get(FAST_LANE_SESSION_KEY)
        if isinstance(pending, dict) and pending.get("awaiting_clarification"):
            orig = pending.get("original_query", "")
            # Synthesise a single clean message the LLM can act on directly.
            combined = (
                f"{orig}\n\n"
                f"User selected / clarified: {message}\n\n"
                "Now complete the original task using the selection above. "
                "Do NOT re-search employees — proceed straight to the target lookup."
            )
            return [{"role": "user", "content": combined}]
        return [{"role": "user", "content": message}]

    async def handle(
        self,
        *,
        message: str,
        context: ContextStack,
        language: str = "en",
    ) -> dict[str, Any]:
        """Run the agentic tool-use loop. Returns dict with 'text' and 'tools_called'."""
        from gateway.core.gateway_tool_executor import GatewayToolExecutor

        sf = context.working_memory.session_facts
        pending = sf.get(FAST_LANE_SESSION_KEY)
        is_continuation = isinstance(pending, dict) and bool(pending.get("awaiting_clarification"))
        original_query = pending.get("original_query", message) if is_continuation else message

        executor = GatewayToolExecutor(
            self._adapter,
            session_id=self._session_id,
            user_message=message,
            user=self._user,
        )
        tools = list(UNIVERSAL_ODOO_TOOL_DEFINITIONS)
        system_prompt = self._build_system_prompt(context, is_continuation)
        messages = self._build_messages(message, context)
        tools_called: list[str] = []
        client = self._get_client()
        response = None

        for _turn in range(FAST_LANE_MAX_TURNS):
            started = time.perf_counter()
            try:
                response = await client.messages.create(
                    model=FAST_LANE_MODEL,
                    max_tokens=FAST_LANE_MAX_TOKENS,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
            except Exception as exc:
                logger.error("[FastLane] Claude API error: %s", exc)
                return {
                    "text": "I encountered an error processing your request. Please try again.",
                    "tools_called": tools_called,
                    "awaiting_clarification": False,
                    "original_query": original_query,
                }

            try:
                from gateway.metrics import record_claude_response
                record_claude_response(response, time.perf_counter() - started, model=FAST_LANE_MODEL)
            except Exception:
                pass

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                logger.warning("[FastLane] unexpected stop_reason=%s", response.stop_reason)
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = []
            for block in tool_blocks:
                tools_called.append(block.name)
                logger.info("[FastLane] tool=%s input=%r", block.name, dict(block.input or {}))
                try:
                    result = await executor.execute(block.name, dict(block.input or {}), context)
                    result_str = json.dumps(result, default=str)
                    if len(result_str) > TOOL_RESULT_CHAR_LIMIT:
                        result_str = result_str[:TOOL_RESULT_CHAR_LIMIT] + "..."
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_str}
                    )
                except Exception as exc:
                    logger.warning("[FastLane] tool %s failed: %s", block.name, exc)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Tool error: {exc}",
                            "is_error": True,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("[FastLane] max turns reached session=%s", self._session_id)

        text = ""
        if response is not None:
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
        if not text:
            text = "I was unable to produce a response. Please rephrase your question."

        text = text.strip()
        awaiting = _response_is_question(text)

        return {
            "text": text,
            "tools_called": tools_called,
            "awaiting_clarification": awaiting,
            "original_query": original_query,
        }


def persist_fast_lane_state(
    session_id: str,
    context: ContextStack,
    *,
    original_query: str,
    last_response: str,
    awaiting_clarification: bool,
) -> None:
    """Store fast-lane context in session so follow-up turns route correctly."""
    from gateway.session_scope import SessionScopeStore

    if awaiting_clarification:
        state: dict[str, Any] = {
            "original_query": original_query,
            "last_response": last_response,
            "awaiting_clarification": True,
        }
        logger.debug("[FastLane] Persisting pending state original_query=%r", original_query)
    else:
        state = {}
        logger.debug("[FastLane] Clearing pending state (answer delivered)")

    context.working_memory.session_facts[FAST_LANE_SESSION_KEY] = state
    if session_id:
        current = SessionScopeStore.get(session_id)
        current[FAST_LANE_SESSION_KEY] = state
        SessionScopeStore._memory[session_id] = current
