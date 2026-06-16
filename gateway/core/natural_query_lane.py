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
import re
import time
from typing import Any

import anthropic

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent
from gateway.tools.universal_odoo import UNIVERSAL_ODOO_TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

from gateway.model_config import AGENT_MODEL as FAST_LANE_MODEL
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

# Pronoun references to payslip session context ("that payslip", "this payslip").
# When detected alongside session last_payslip_scope, route to fast lane to
# resolve using session data rather than treating as a new payroll search.
_PAYSLIP_PRONOUN_RE = re.compile(
    r"\b(?:that|this|the\s+(?:same|above|previous|last))\s+payslip\b"
    r"|\bfrom\s+(?:that|this|the\s+same)\s+payslip\b",
    re.IGNORECASE,
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
  Requests     : employee.requests (fields: employee_id, request_type, state, date_start, date_end)
                  request_type: "leave", "loan", "advance", "job_mission", "termination"
  Projects     : project.project (fields: name, partner_id, contract_amount)
  Partners     : res.partner
  Departments  : hr.department

HOW TO ANSWER:
1. Read the query carefully. Handle typos and natural phrasing (Arabic/Urdu mixed in).
2. Identify entities (person names, project names, date hints) and what is being asked about them.
3. For person + data queries ("jawad attendance", "adil khan vehicle", "jawad payslip for may"):
   - Step 1: query_odoo hr.employee with [["name","ilike","<name>"]], limit=5.
   - Extract ONLY the name from the query (e.g. "jawad" from "show me jawad payslip for may 2026").
   - If ONE match: immediately proceed to step 2.
   - If MULTIPLE matches: list names + IDs and ask which one. Stop — do NOT proceed.
4. When the user confirms an employee by name or ID, go DIRECTLY to the related record.
   Do NOT re-search employees. Use the ID provided and query the target model.
5. Use introspect_odoo_schema when unsure of field names.
6. If no data found, explain and ask for more detail.

ATTENDANCE LOOKUP PATTERN:
  After getting employee_id, query hr.attendance:
    domain: [["employee_id","=",<id>], ["check_in",">=","<date_from>"], ["check_in","<=","<date_to>"]]
    fields: ["employee_id","check_in","check_out","worked_hours"]
  Summarise total days present, hours worked. Do not return raw list of 50 rows.

PAYSLIP LOOKUP PATTERN:
  After getting employee_id, query hr.payslip using name pattern match OR date overlap.
  Elrace payslips run mid-month to mid-month (e.g. Mar-21 to Apr-20 for "March").
  Use the OR domain below — do NOT use date_to <= month_end as it will miss these payslips.

  PREFERRED — name-based (most reliable for Elrace):
    domain: ["|", ["name","ilike","<Mon-YYYY>"], "&", ["date_from","<=","<month_end>"], ["date_to",">=","<month_start>"]]
    e.g. for March 2026: ["|",["name","ilike","Mar-2026"],"&",["date_from","<=","2026-03-31"],["date_to",">=","2026-03-01"]]

  FALLBACK — date_from only (if the above returns nothing):
    domain: [["employee_id","=",<id>], ["date_from",">=","<month_start>"], ["date_from","<=","<month_end>"]]

  fields: ["name","date_from","date_to","net_wage","fine","advance","total_deductions","pension","unemployment_insurance"]
  Return a clean formatted summary. If no payslip found for that period, say so clearly with the period requested.

LEAVE / REQUEST LOOKUP PATTERN:
  Model: employee.requests  ← NOTE: plural "requests" not "request"
  Fields: employee_id, request_type, state, date_start, date_end, name
  request_type values: "leave", "loan", "advance", "job_mission", "termination"
  After getting employee_id:
    For leave COUNT this month: aggregate_odoo("employee.requests",
        [["employee_id","=",<id>], ["request_type","=","leave"],
         ["date_start",">=","<period_start>"], ["date_start","<=","<period_end>"]],
        [], ["id:count"])
    For leave LIST/HISTORY: query_odoo("employee.requests",
        [["employee_id","=",<id>], ["request_type","=","leave"]],
        ["name","date_start","date_end","state"], limit=20)
  Do NOT use employee.request (singular) — it does not exist.
  Do NOT route leave queries to hr.payslip.

LEAVE BALANCE / ALLOCATION PATTERN:
  "Remaining leave balance" = how many days are left in the employee's allocation.
  Model: hr.leave.allocation
  Fields: employee_id, holiday_status_id, number_of_days, number_of_days_display,
          state, date_from, date_to
  Query: query_odoo("hr.leave.allocation",
      [["employee_id","=",<id>], ["state","=","validate"]],
      ["holiday_status_id","number_of_days","number_of_days_display","date_from","date_to"])
  If hr.leave.allocation returns nothing, try hr.leave.type for annual entitlements.
  ALWAYS use the ID from session context — do NOT re-search employees.

IMPORTANT — VEHICLE LOOKUP PATTERN:
  After confirming employee_id, ALWAYS use this domain:
    ["|", ["employee_id","=", <id>], ["driver_id","=", <id>]]
  If that returns nothing, try:
    [["employee_id.name","ilike","<name>"]]

IMPORTANT — PAYSLIP PRONOUN RESOLUTION:
  When the query contains "that payslip", "this payslip", or "the same payslip" AND the
  session context includes "Last payslip scope", use those session values directly:
    - employee_id from the scope to filter hr.payslip
    - date_from / date_to if available
  Do NOT ask for clarification — resolve from the session context.

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

IMPORTANT — RESPONSE STYLE:
  - Give a COMPLETE answer. Do NOT end with "Would you like more details?" or
    "Shall I show more?" — the UI provides follow-up suggestion chips automatically.
  - Only end with a question when you need the user to CHOOSE between options
    (disambiguation). Format as a numbered list (1. / 2. / 3.) with a "?" in the text.
  - Any other "?" in the response will break the follow-up suggestion system.
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

    # Signal 3: pronoun reference to last payslip ("give me deduction for that payslip")
    # Only fires when session actually has last_payslip_scope — otherwise let payroll handle it.
    if _PAYSLIP_PRONOUN_RE.search(message):
        if context is not None:
            lps = context.working_memory.session_facts.get("last_payslip_scope")
            if isinstance(lps, dict) and lps:
                logger.debug("[FastLane] Signal 3 — payslip pronoun with session scope=%r", lps)
                return True

    # Signal 4: payslip/salary lookup with a named entity.
    # The payroll pipeline's name-extraction is brittle for natural phrasings like
    # "show me jawad payslip for may 2026" — Claude in fast lane handles this cleanly.
    if (
        intent.subject_area in ("hr", "payroll", "other", "general")
        and intent.primary_action in ("fetch_data", "search_entity", "analyze", "ask_question", "other")
        and any(w in msg_lower for w in ("payslip", "salary", "net salary", "net pay"))
        and bool(intent.entities)
    ):
        logger.debug("[FastLane] Signal 4 — payslip lookup with entity=%r", [e.value for e in intent.entities])
        return True

    # Signal 5: attendance / leave / request lookup with a named entity.
    # These queries misfire through HR/payroll pipelines; fast lane resolves the
    # person first then fetches the correct model directly.
    if (
        any(w in msg_lower for w in (
            "attendance", "absent", "check in", "check out", "check-in", "check-out",
            "leave", "leaves", "vacation", "day off", "annual leave",
            "request", "requests", "loan", "advance", "mission",
        ))
        and bool(intent.entities)
    ):
        logger.debug("[FastLane] Signal 5 — HR-entity lookup with entity=%r", [e.value for e in intent.entities])
        return True

    # Signal 6: visa/passport/document expiry queries — best handled by fast lane
    # which can filter hr.employee by expiry date fields directly.
    if any(w in msg_lower for w in ("visa expir", "passport expir", "expiring visa", "expiring passport",
                                     "labour card expir", "labor card expir", "document expir")):
        logger.debug("[FastLane] Signal 6 — document expiry query")
        return True

    # Signal 7: fleet/vehicle query with a named entity (person name).
    # "Adil Khan vehicle", "show car for Ahmed" → need employee lookup first.
    # subject_area='fleet' with entities means cross-entity (person → vehicle).
    if (
        intent.subject_area == "fleet"
        and any(w in msg_lower for w in ("vehicle", "vehicles", "car", "cars"))
        and bool(intent.entities)
    ):
        logger.debug("[FastLane] Signal 7 — fleet query with named entity=%r", [e.value for e in intent.entities])
        return True

    return False


def _response_is_question(text: str) -> bool:
    """True only when Claude is asking for a USER CHOICE (disambiguation).

    Polite follow-up offers ("Would you like more details?") must NOT count —
    they have a "?" but no numbered options, so the user cannot meaningfully
    "select" an answer. Only flag awaiting_clarification when Claude listed
    numbered choices AND included a question mark anywhere in the response.
    """
    import re as _re
    stripped = text.rstrip()
    if "?" not in stripped:
        return False
    # True disambiguation: "?" present AND numbered option list (1. / 2. / 3.)
    return bool(_re.search(r"^\s*[1-9][.)]\s+", stripped, _re.MULTILINE))


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
            # Inject previously resolved employee so follow-up chips don't re-disambiguate.
            entity = sf.get("last_fast_lane_entity")
            if isinstance(entity, dict) and entity.get("id"):
                session_context_lines.append(
                    f"Previously resolved employee: {entity['name']} (ID: {entity['id']}). "
                    f"If the current query is about this employee, use ID={entity['id']} "
                    f"directly — do NOT re-search hr.employee."
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
