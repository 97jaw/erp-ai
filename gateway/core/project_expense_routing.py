"""Project expense tool selection and system-prompt guidance (Phase E2)."""

from __future__ import annotations

import re
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_query_utils import looks_like_project_cost_query
from gateway.core.working_memory import ActiveContext
from gateway.tool_validation import extract_project_id_from_text

PROJECT_EXPENSE_PROMPT_SECTION = """
PROJECT EXPENSE QUERY HANDLING:

When the user asks about project expenses, use these tools in this order:

1. ENTITY RESOLUTION FIRST
   - Resolve project name(s) using EntityResolver / entity gate
   - Confirm with the user if ambiguous
   - Obtain project_id(s) before any expense tool call

2. CHOOSE THE RIGHT TOOL

   User intent → Tool to call:

   "Show me costs/expenses for [project]"     → get_project_expense_summary
   "Show project [X] spending overview"        → get_project_expense_summary
   "How much have we spent on [X]"             → get_project_expense_summary
   "Is [X] over budget" (single project)       → get_project_expense_summary

   "Break down [X] by account/GL"              → get_project_expense_breakdown
   "Show GL details for [X]"                   → get_project_expense_breakdown
   "Where exactly did money go in [X]"         → get_project_expense_breakdown
   "Drill into materials for [X]"              → get_project_expense_breakdown (+ main_group_filter)
   Follow-up "show full breakdown"             → get_project_expense_breakdown (reuse last project_id)

   "Compare [A] and [B] costs"                 → compare_project_expenses
   "Which [group] projects are over budget"    → compare_project_expenses (2+ project_ids)
   "Top N projects by expense" (named set)     → compare_project_expenses

   Prefer get_project_expense_summary over legacy get_project_expenses for cost overview.
   Use get_project_expense_breakdown only for GL/account drill-down (not trade categories).
   Use compare_project_expenses only when comparing 2–10 projects side-by-side.

3. NEVER call breakdown without summary first
   Unless the user EXPLICITLY asks for GL/account drill-down, start with summary.

4. RESPONSE PATTERN FOR SUMMARY
   Lead with spend status (over/under budget, spend % of W.O)
   Then top 3 trade categories
   Then notable variances or alerts
   Offer: "Want me to break this down by account?"

5. RESPONSE PATTERN FOR BREAKDOWN
   Present MG → SG → Account hierarchy; top main groups first
   Offer drill-down into a specific group

6. RESPONSE PATTERN FOR COMPARISON
   Ranked table, combined totals, which project is most concerning
   Offer: "Drill into [project name]?"

KNOWN BUSINESS CONTEXT:
- W.O amount = Work Order total (budget/agreement) — field wo_amount from tool
- total_expenses = operational spend (petty + labor + LPO + bills)
- spend_percent_of_wo = (total_expenses / wo_amount) × 100 — only when wo_amount > 0
- spend_status / status_label = honest interpretation from the tool (use these in narration)
- Above 100% means over budget
- top_expenses = TRADE categories (civil, electrical, mechanical, etc.)
- GL breakdown groups = ACCOUNT level (different from trade categories)

PROJECT EXPENSE NARRATION RULES:

When spend_status is "no_budget_assigned":
  Say the project has recorded expenses but no W.O budget is assigned, so no spend
  percentage or budget status is available. DO NOT say "X% of W.O" or "On track."

When spend_status is "no_data":
  Say the project was found but no expenses are recorded yet.

When top_expenses show a category with AED 0 but a percentage:
  Show only categories with non-zero amounts, OR explain the percentage base differs.
"""

PROJECT_EXPENSE_TOOL_SOURCES = frozenset(
    {
        "project_expense_summary",
        "project_expense_summary_mobile",
        "project_expense_dashboard",
        "project_expense_breakdown_mobile",
        "compare_project_expenses",
    },
)


def is_project_expense_tool_result(payload: Any) -> bool:
    """Return True when a tool payload came from the mobile expense intelligence APIs."""
    return isinstance(payload, dict) and payload.get("_source") in PROJECT_EXPENSE_TOOL_SOURCES


_COMPARE_SIGNALS = (
    "compare",
    " vs ",
    "versus",
    "side by side",
    "boys and girls",
    "girls and boys",
)

_BREAKDOWN_SIGNALS = (
    "break down",
    "breakdown",
    "cost breakdown",
    "cost break down",
    "by account",
    "gl detail",
    "gl details",
    "gl breakdown",
    "where exactly",
    "where did the money",
    "drill into",
    "full breakdown",
    "show gl",
    "account level",
    "by gl",
    "breakdown as well",
)

_FOLLOW_UP_BREAKDOWN_SIGNALS = (
    "full breakdown",
    "show breakdown",
    "break it down",
    "breakdown by account",
    "as well",
    "also show",
    "show me cost",
)

FOLLOW_UP_SIGNALS = (
    "breakdown",
    "break down",
    "drill down",
    "drill into",
    "show more",
    "more detail",
    "the detail",
    "expand",
    "as well",
    "also",
    "and the",
    "what about",
    "share the",
    "give me the",
    "show the",
    "التفاصيل",
    "بالتفصيل",
    "أيضا",
)


def is_followup_to_active(
    query: str,
    intent: Intent,
    active: ActiveContext | None,
) -> bool:
    """Return True when the query is a follow-up about the active project."""
    if active is None or active.project_id is None:
        return False

    for entity in intent.entities:
        if entity.type != "project":
            continue
        val = entity.value.strip().lower()
        if val == str(active.project_id):
            return True
        active_name = (active.project_name or "").lower()
        if active_name and active_name in val:
            return True
        if active_name and val in active_name:
            return True
        return False

    query_lower = query.lower()
    return any(signal in query_lower for signal in FOLLOW_UP_SIGNALS)


def apply_active_follow_up_context(context: ContextStack, active: ActiveContext) -> None:
    """Inject active project into session facts and skip entity discovery."""
    from gateway.core.entity_gate import EntityGate

    context.working_memory.touch_active()
    EntityGate.apply_confirmed_entities(
        context,
        {
            "project": {
                "id": active.project_id,
                "name": active.project_name or f"Project {active.project_id}",
            },
        },
    )

_MATERIALS_FILTER = re.compile(r"\bmaterials?\b", re.IGNORECASE)
_ARABIC_EXPENSE = re.compile(r"تكاليف|مصروف|تكلفة")


def is_project_expense_query(message: str, intent: Intent) -> bool:
    """Return True when the query is about project expense intelligence tools."""
    if intent.primary_action == "search_entity":
        return False
    blob = _query_blob(message, intent)
    if any(signal in blob for signal in _BREAKDOWN_SIGNALS):
        return True
    if any(signal in blob for signal in _COMPARE_SIGNALS):
        return True
    if "over budget" in blob:
        return True
    if re.search(r"\bgl\b", blob):
        return True
    if any(token in blob for token in ("money", "spend", "spent", "spending", "status")):
        return True
    if intent.subject_area == "project" and intent.primary_action in {
        "fetch_data",
        "analyze",
        "compare",
        "generate_report",
    }:
        if any(token in blob for token in ("cost", "expense", "spending", "budget", "money")):
            return True
    if _ARABIC_EXPENSE.search(blob):
        return True
    return looks_like_project_cost_query(message, subject_area=intent.subject_area)


def select_project_expense_tool(
    message: str,
    intent: Intent,
    context: ContextStack,
) -> tuple[str, dict[str, Any]] | None:
    """Choose summary, breakdown, or compare tool with input payload."""
    if not is_project_expense_query(message, intent):
        return None

    blob = _query_blob(message, intent)
    project_ids = _collect_project_ids(message, intent, context)

    if _is_compare_query(blob, intent):
        compare_ids = _compare_project_ids(project_ids, intent, context)
        if len(compare_ids) >= 2:
            return "compare_project_expenses", {"project_ids": compare_ids[:10]}

    if _is_breakdown_query(blob, intent, context):
        project_id = _require_single_project_id(project_ids, context)
        tool_input: dict[str, Any] = {"project_id": project_id}
        mg_filter = _extract_main_group_filter(blob)
        if mg_filter:
            tool_input["main_group_filter"] = mg_filter
        return "get_project_expense_breakdown", tool_input

    project_id = _require_single_project_id(project_ids, context)
    return "get_project_expense_summary", {"project_id": project_id}


def resolve_project_expense_tool_for_strategy(
    intent: Intent,
    context: ContextStack,
) -> tuple[str, dict[str, Any]]:
    """Strategy-planner entry point using intent text as the message."""
    from gateway.core.entity_gate import EntityGate

    message = intent.specific_intent
    selected = select_project_expense_tool(message, intent, context)
    if selected is None:
        raise ValueError("Not a project expense intelligence query")

    tool_name, _tool_input = selected
    if tool_name == "compare_project_expenses":
        return selected

    if EntityGate.has_active_project_scope(context) or _collect_project_ids(message, intent, context):
        return selected

    raise ValueError("Project must be confirmed before project expense tools")


def _query_blob(message: str, intent: Intent) -> str:
    return f"{message} {intent.specific_intent}".lower()


def _is_compare_query(blob: str, intent: Intent) -> bool:
    if intent.primary_action == "compare" and intent.subject_area == "project":
        return True
    if "which" in blob and "over budget" in blob:
        return True
    if len([entity for entity in intent.entities if entity.type == "project"]) >= 2:
        return any(signal in blob for signal in _COMPARE_SIGNALS) or "compare" in blob
    return any(signal in blob for signal in _COMPARE_SIGNALS)


def _is_breakdown_query(blob: str, intent: Intent, context: ContextStack) -> bool:
    if any(signal in blob for signal in _BREAKDOWN_SIGNALS):
        return True
    if any(signal in blob for signal in _FOLLOW_UP_BREAKDOWN_SIGNALS):
        scope_id = context.working_memory.session_facts.get("resolved_project_id")
        if scope_id or context.working_memory.session_facts.get("last_expense_summary_project_id"):
            return True
    if intent.primary_action == "analyze" and "break" in blob:
        return True
    return False


def _extract_main_group_filter(blob: str) -> str | None:
    if _MATERIALS_FILTER.search(blob):
        return "materials"
    match = re.search(r"(?:drill into|breakdown for|filter to)\s+([a-z0-9 _-]{3,40})", blob)
    if match:
        return match.group(1).strip()
    return None


def _collect_project_ids(
    message: str,
    intent: Intent,
    context: ContextStack,
) -> list[int]:
    ids: list[int] = []
    facts = context.working_memory.session_facts

    active = context.working_memory.get_active_project()
    if active and active.project_id is not None:
        ids.append(int(active.project_id))

    confirmed = facts.get("confirmed_entities") or {}
    project = confirmed.get("project") or {}
    if project.get("id"):
        ids.append(int(project["id"]))

    for key in ("resolved_project_id", "last_expense_summary_project_id"):
        value = facts.get(key)
        if value is not None:
            pid = int(value)
            if pid not in ids:
                ids.append(pid)

    extra = facts.get("resolved_project_ids") or facts.get("compare_project_ids") or []
    for value in extra:
        pid = int(value)
        if pid not in ids:
            ids.append(pid)

    for entity in intent.entities:
        if entity.type != "project":
            continue
        if entity.value.isdigit():
            pid = int(entity.value)
            if pid not in ids:
                ids.append(pid)

    extracted = extract_project_id_from_text(message) or extract_project_id_from_text(
        intent.specific_intent,
    )
    if extracted is not None and extracted not in ids:
        ids.append(extracted)

    return ids


def _compare_project_ids(
    project_ids: list[int],
    intent: Intent,
    context: ContextStack,
) -> list[int]:
    facts = context.working_memory.session_facts
    explicit = facts.get("compare_project_ids") or facts.get("resolved_project_ids")
    if explicit:
        return [int(value) for value in explicit]
    if len(project_ids) >= 2:
        return project_ids
    if len(intent.entities) >= 2:
        default_pairs = facts.get("zayidia_compare_defaults")
        if default_pairs:
            return [int(value) for value in default_pairs]
    return project_ids


def _require_single_project_id(project_ids: list[int], context: ContextStack) -> int:
    if project_ids:
        return project_ids[0]
    resolved = context.working_memory.session_facts.get("resolved_project_id")
    if resolved is not None:
        return int(resolved)
    raise ValueError("Project expense tool requires a resolved project_id")
