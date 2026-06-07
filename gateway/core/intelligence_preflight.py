"""Intent analysis and entity resolution preflight for the agent system prompt."""

from __future__ import annotations

from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.entity_resolver import (
    Decision,
    EntityResolver,
    OdooProjectSearch,
    ResolutionResult,
    ResolutionStrategy,
)
from gateway.core.intent_analyzer import Intent, IntentAnalyzer


async def build_intelligence_preflight_section(
    user_message: str,
    context_stack: ContextStack,
    adapter: Any | None = None,
) -> str:
    """Analyze intent and resolve entities before the agent loop runs."""
    analyzer = IntentAnalyzer()
    intent = await analyzer.analyze(user_message, context_stack)
    sections: list[str] = []

    if intent.out_of_scope:
        sections.append(_format_out_of_scope_prompt(intent))
        return "\n".join(sections)

    if adapter is None:
        return ""

    resolver = EntityResolver(OdooProjectSearch(adapter))
    decision_engine = ResolutionStrategy()
    for entity in intent.entities:
        if entity.type != "project":
            continue
        result = await resolver.resolve_project(entity.value, context_stack)
        decision = decision_engine.decide(result, context_stack)
        sections.append(_format_project_resolution_prompt(entity.value, result, decision))

    if sections:
        sections.insert(
            0,
            "ENTITY RESOLUTION OVERRIDE:\n"
            "- Discovery search results are listed below.\n"
            "- Do NOT call financial or KPI tools until the user confirms the exact record.\n"
            "- Present candidates and ask the user to confirm before fetching costs or financial data.",
        )
    return "\n".join(sections)


def _format_out_of_scope_prompt(intent: Intent) -> str:
    reason = intent.out_of_scope_reason or "This capability is unavailable."
    return f"""
OUT OF SCOPE QUERY DETECTED:
{reason}

MANDATORY RESPONSE RULES:
- Do NOT call Odoo tools or HR/payroll tools for this request
- Do NOT claim a database error, system error, connection issue, or operation in progress
- Do NOT tell the user to try again later
- Respond honestly that payroll/payslip access is not available in this assistant
- Provide the alternative from the reason above when available
- Keep the response short and direct
"""


def _format_project_resolution_prompt(
    entity_query: str,
    result: ResolutionResult,
    decision: Decision,
) -> str:
    lines = [f"\nPROJECT RESOLUTION for query fragment: {entity_query!r}"]
    if decision.match is not None:
        entity = decision.match.entity
        lines.append(
            f"- Top match: {entity.get('name')} "
            f"(id={entity.get('id')}, confidence={decision.match.confidence:.2f})"
        )
    if decision.alternatives:
        alt_names = [
            str(match.entity.get("name") or "unknown")
            for match in decision.alternatives[:5]
        ]
        lines.append(f"- Alternatives: {', '.join(alt_names)}")

    action_instructions = {
        "show_candidates": (
            "Present the candidate list and ask the user to confirm one record "
            "before calling get_project_expenses or any financial KPI tool."
        ),
    }
    instruction = action_instructions.get(
        decision.action,
        "Ask the user to confirm the correct record before any financial tool call.",
    )
    lines.append(f"- Decision: {decision.action}")
    lines.append(f"- Instruction: {instruction}")
    if decision.note:
        lines.append(f"- Note: {decision.note}")
    lines.append(f"- Total matches found: {result.total_matches}")
    return "\n".join(lines)
