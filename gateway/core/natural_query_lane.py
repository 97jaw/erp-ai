"""Natural Query Fast Lane — agentic fallback when the pipeline cannot classify a query.

When the intent analyzer signals uncertainty (subject_area='other' or ambiguous
cross-entity phrasing like "Adil Khan vehicle"), bypass the rigid pipeline and
let Claude reason directly with all tools available.

CRITICAL FOR FOLLOW-UPS:
  When the fast lane asks a disambiguation question ("which Adil Khan?"), the
  user's reply must also go through the fast lane — NOT the entity gate.
  We achieve this by persisting a 'fast_lane_pending' slot in the session store
  and checking it in should_use_fast_lane() on every subsequent turn.
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

# Session key used to persist fast-lane state across HTTP turns.
FAST_LANE_SESSION_KEY = "fast_lane_pending"

# Cross-entity signals: words that suggest the query spans multiple Odoo models
# and that the rigid pipeline (which resolves a single entity type) is likely to fail.
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
1. Read the query carefully. Handle typos and natural phrasing (e.g. Arabic/Urdu mixed in).
2. Identify entities (person names, project names, date hints) and what is being asked.
3. For cross-entity queries ("Adil Khan vehicle"), decompose: first find the employee,
   then use their id to find the related record.
4. Call tools sequentially. Use introspect_odoo_schema when unsure of field names.
5. If multiple records match a name, list them and ask which one — do NOT guess.
6. If the user's message is a reply to your previous disambiguation question,
   use the full name/ID they provided to continue the lookup you were doing.
7. If no data is found, explain what you searched and ask for more detail.

EXAMPLES:

Turn 1 — User: "Adil Khan vehicle"
  → query_odoo("hr.employee", [["name","ilike","Adil Khan"]], ["id","name","file_id"], limit=5)
  → If multiple: "I found 3 employees named Adil Khan: [1] Adil Khan Sher Dil Khan ..."
    "Which one would you like? I'll find their vehicle once you confirm."
  → If one: query_odoo("fleet.vehicle",
        ["|", ["employee_id","=", id], ["driver_id.name","ilike","Adil Khan"]],
        ["name","license_plate","model_id","state_id"], limit=5)
    then show vehicle details.

Turn 2 — User: "Adil Khan Sher Dil Khan" (reply to the disambiguation above)
  → This is a clarification of the previous question about VEHICLES.
  → query_odoo("hr.employee", [["name","ilike","Adil Khan Sher Dil Khan"]], ["id","name"], limit=3)
  → query_odoo("fleet.vehicle", [["employee_id","=", employee_id]],
        ["name","license_plate","model_id","state_id"], limit=5)
  → Show the vehicle. DO NOT ask about financial data. This is a vehicle query.

User: "vehicles needing insurance renewal"
  → query_odoo("fleet.vehicle",
        [["insurance_expiry_date","<=", <next_month_date>]],
        ["name","license_plate","insurance_expiry_date","employee_id"], limit=50)
  → List the vehicles and their expiry dates.

PERMISSIONS:
  - Read-only. Never call create/write/unlink on any model.
  - System models (res.users, ir.config_parameter) are forbidden.

ASK, DON'T REFUSE:
  Bad:  "Is this the one you want financial data for?"   ← WRONG, never say this
  Good: "I found them. Now looking up their vehicle..."
  Bad:  "No employee found matching X"
  Good: "I searched for X but found no match — did you mean Y?"

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

    Fires when:
    1. The intent classifier expressed uncertainty (subject_area='other')
    2. The session has an active fast-lane follow-up pending (disambiguation reply)
    3. Natural cross-entity phrasing with a 'general' subject
    """
    # Signal 0 (highest priority): active fast-lane follow-up — the user is
    # replying to the fast lane's disambiguation question.
    if context is not None:
        pending = context.working_memory.session_facts.get(FAST_LANE_SESSION_KEY)
        if isinstance(pending, dict) and pending.get("awaiting_clarification"):
            logger.debug("[FastLane] Follow-up detected — routing to fast lane (pending=%r)", pending)
            return True

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
    """True when Claude's response ends with a question (disambiguation pending)."""
    stripped = text.rstrip()
    return stripped.endswith("?") or "?" in stripped[-120:]


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

    def _build_system_prompt(self, context: ContextStack, prior_turn: dict | None) -> str:
        from datetime import date

        today = date.today().isoformat()
        session_context_lines: list[str] = []
        sf = context.working_memory.session_facts

        # Include fast-lane prior turn so Claude knows what it was doing
        pending = sf.get(FAST_LANE_SESSION_KEY)
        if isinstance(pending, dict) and pending.get("awaiting_clarification"):
            session_context_lines.append(
                f"PRIOR FAST-LANE CONTEXT: The user was asked: \"{pending.get('last_response', '')}\"\n"
                f"Original query that started this flow: \"{pending.get('original_query', '')}\"\n"
                "The user's current message is their answer to that question. "
                "Continue the lookup you were doing — do NOT start over or ask about financial data."
            )

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
        """Build messages list, prepending prior fast-lane turn if available."""
        messages: list[dict[str, Any]] = []
        sf = context.working_memory.session_facts
        pending = sf.get(FAST_LANE_SESSION_KEY)
        if isinstance(pending, dict) and pending.get("awaiting_clarification"):
            # Reconstruct the prior turn so Claude has full context
            orig_query = pending.get("original_query", "")
            last_response = pending.get("last_response", "")
            if orig_query and last_response:
                messages.append({"role": "user", "content": orig_query})
                messages.append({"role": "assistant", "content": last_response})
        messages.append({"role": "user", "content": message})
        return messages

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
        original_query = (
            pending.get("original_query", message)
            if isinstance(pending, dict)
            else message
        )

        executor = GatewayToolExecutor(
            self._adapter,
            session_id=self._session_id,
            user_message=message,
            user=self._user,
        )
        tools = list(UNIVERSAL_ODOO_TOOL_DEFINITIONS)
        system_prompt = self._build_system_prompt(context, prior_turn=pending)
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

            # Execute tools
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

        # Extract final text
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
        # Keep the conversation alive — next turn will also go to fast lane
        state = {
            "original_query": original_query,
            "last_response": last_response,
            "awaiting_clarification": True,
        }
        logger.debug("[FastLane] Persisting pending state original_query=%r", original_query)
    else:
        # Conversation complete — clear the fast-lane pending flag
        state = {}
        logger.debug("[FastLane] Clearing pending state (answer delivered)")

    context.working_memory.session_facts[FAST_LANE_SESSION_KEY] = state
    if session_id:
        # Force-write to the session store so the next HTTP request picks it up
        current = SessionScopeStore.get(session_id)
        current[FAST_LANE_SESSION_KEY] = state
        # Use the internal dict directly since update() merges dicts
        SessionScopeStore._memory[session_id] = current
