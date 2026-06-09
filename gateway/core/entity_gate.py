"""Generic entity confirmation gate before entity-bound financial/KPI tool calls."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from gateway.core.context_stack import ContextStack
from gateway.core.entity_resolver import (
    CONFIDENT_CONFIDENCE_MIN,
    EntityResolver,
    OdooProjectSearch,
)
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_query_utils import (
    extract_project_name_hint,
    is_project_expense_follow_up,
    looks_like_project_cost_query,
    meaningful_project_words,
)

logger = logging.getLogger(__name__)

_TRANSIENT_ODOO_ERRORS = frozenset({"request-sent", "idle", "remotedisconnected"})

# Intent often labels schools/facilities as partner; entity gate must search project.project.
_PROJECT_ENTITY_SIGNALS = (
    "school",
    "zayidia",
    "project",
    "renovation",
    "hospital",
    "facility",
    "campus",
    "guard",
    "building",
    "villa",
    "maintenance",
)


def _is_transient_odoo_error(exc: Exception) -> bool:
    message = str(exc).strip().lower()
    if message in _TRANSIENT_ODOO_ERRORS:
        return True
    return "timeout" in message or "connection" in message


def _prefer_project_entity_type(value: str, message: str) -> str:
    """Reclassify partner intents that clearly refer to Odoo projects."""
    blob = f"{message} {value}".lower()
    if looks_like_project_cost_query(message):
        return "project"
    if any(signal in blob for signal in _PROJECT_ENTITY_SIGNALS):
        return "project"
    if extract_project_name_hint(message):
        return "project"
    return "partner"

EntityType = Literal["project", "partner", "account"]
EntityGateStatus = Literal[
    "confirmed",
    "needs_confirmation",
    "weak_confirmation",
    "not_found",
    "not_required",
]

ENTITY_BOUND_FINANCIAL_TOOLS: frozenset[str] = frozenset(
    {
        "get_project_expenses",
        "get_project_financial_data",
        "get_project_cost_categories",
        "get_project_expense_summary",
        "get_project_expense_breakdown",
        "compare_project_expenses",
        "get_projects_by_client",
        "get_top_projects_by_metric",
        "get_projects_with_overrun",
    },
)

TOOL_ENTITY_REQUIREMENTS: dict[str, list[EntityType]] = {
    "get_project_expenses": ["project"],
    "get_project_financial_data": ["project"],
    "get_project_cost_categories": ["project"],
    "get_project_expense_summary": ["project"],
    "get_project_expense_breakdown": ["project"],
    "compare_project_expenses": [],
    "get_projects_by_client": ["partner"],
    "get_top_projects_by_metric": [],
    "get_projects_with_overrun": [],
    "get_purchase_orders": [],
}


@dataclass(frozen=True)
class ConfirmedEntityRef:
    """User-confirmed entity reference from the API."""

    type: str
    id: int
    name: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConfirmedEntityRef | None:
        entity_type = str(payload.get("type") or "").strip()
        entity_id = payload.get("id")
        if not entity_type or entity_id is None:
            return None
        try:
            parsed_id = int(entity_id)
        except (TypeError, ValueError):
            return None
        name = payload.get("name")
        return cls(type=entity_type, id=parsed_id, name=str(name) if name else None)


@dataclass
class EntityGateResult:
    """Outcome of evaluating whether entity-bound tools may run."""

    status: EntityGateStatus
    required_types: list[str] = field(default_factory=list)
    matches: list[dict[str, Any]] = field(default_factory=list)
    options: list[dict[str, Any]] = field(default_factory=list)
    confirmed: dict[str, dict[str, Any]] = field(default_factory=dict)
    query_label: str = ""
    entity_discovery_count: int = 0
    entity_top_confidence: float = 0.0
    entity_strategies_used: list[str] = field(default_factory=list)
    entity_strategy_that_matched: str | None = None


class PartnerDiscoverySearch:
    """Adapter-backed partner discovery (search_read only, no KPI)."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._lock = asyncio.Lock()

    async def search_partners(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        words = meaningful_project_words(query)
        if not words:
            return []
        domain: list[Any] = [["name", "ilike", word] for word in words]
        if len(words) > 1:
            domain = ["&"] * (len(words) - 1) + domain

        async with self._lock:
            def _call() -> list[dict[str, Any]]:
                return self._adapter.search_read(
                    model="res.partner",
                    domain=domain,
                    fields=["id", "name", "is_company"],
                    limit=limit,
                )

            return await asyncio.to_thread(_call)


class EntityGate:
    """Resolve entities via discovery search; require confirmation before financial tools."""

    def __init__(
        self,
        adapter: Any,
        *,
        project_resolver: EntityResolver | None = None,
    ) -> None:
        self._adapter = adapter
        self._project_resolver = project_resolver or EntityResolver(OdooProjectSearch(adapter))
        self._partner_search = PartnerDiscoverySearch(adapter)

    @staticmethod
    def tool_requires_entity(tool_name: str) -> list[str]:
        return list(TOOL_ENTITY_REQUIREMENTS.get(tool_name, []))

    @staticmethod
    def is_entity_bound_financial_tool(tool_name: str) -> bool:
        return tool_name in ENTITY_BOUND_FINANCIAL_TOOLS

    @staticmethod
    def infer_entity_hints(message: str, intent: Intent) -> Intent:
        """Add entity references inferred from natural-language hints."""
        entities = list(intent.entities)
        if not any(entity.type == "project" for entity in entities):
            if looks_like_project_cost_query(message, subject_area=intent.subject_area):
                if not is_project_expense_follow_up(message):
                    hint = extract_project_name_hint(message)
                    if hint:
                        entities.append(EntityReference(type="project", value=hint, confidence=0.85))

        partner_entity = next((entity for entity in entities if entity.type == "partner"), None)
        if partner_entity is None and "client" in message.lower():
            for entity in entities:
                if entity.type == "project":
                    break
            else:
                lowered = message.lower()
                if " for " in lowered and "client" in lowered:
                    fragment = message.split(" for ", 1)[-1].strip()
                    if fragment and len(fragment) > 2:
                        entities.append(EntityReference(type="partner", value=fragment, confidence=0.7))

        from dataclasses import replace
        from gateway.core.project_expense_routing import is_project_expense_query

        updates: dict[str, Any] = {}
        if entities != intent.entities:
            updates["entities"] = entities

        if (
            looks_like_project_cost_query(message, subject_area=intent.subject_area)
            or is_project_expense_query(message, intent)
        ) and intent.primary_action != "search_entity":
            updates["subject_area"] = "project"
            if intent.primary_action in {"other"}:
                updates["primary_action"] = "fetch_data"

        if not updates:
            return intent
        return replace(intent, **updates)

    @staticmethod
    def infer_required_entities(
        message: str,
        intent: Intent,
        context: ContextStack | None = None,
    ) -> list[tuple[str, str]]:
        """Return (entity_type, query_value) pairs that must be confirmed."""
        if (
            context is not None
            and is_project_expense_follow_up(message)
            and EntityGate.has_active_project_scope(context)
        ):
            return []

        required: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add(entity_type: str, value: str) -> None:
            key = (entity_type, value.strip().lower())
            if not value.strip() or key in seen:
                return
            seen.add(key)
            required.append((entity_type, value.strip()))

        query_blob = f"{message} {intent.specific_intent} {intent.subject_area}".lower()
        needs_project = looks_like_project_cost_query(query_blob) or any(
            token in query_blob
            for token in ("cost", "costs", "expense", "expenses", "spending", "budget")
        )
        needs_partner = "client" in query_blob or intent.subject_area == "client"

        for entity in intent.entities:
            if entity.type in {"project", "partner", "account"}:
                entity_type = entity.type
                if entity_type == "partner":
                    entity_type = _prefer_project_entity_type(entity.value, message)
                add(entity_type, entity.value)

        if needs_project and not any(item[0] == "project" for item in required):
            hint = extract_project_name_hint(message)
            if hint:
                add("project", hint)

        if needs_partner and not any(item[0] == "partner" for item in required):
            if " for " in message.lower():
                fragment = message.split(" for ", 1)[-1].strip()
                if fragment:
                    add("partner", fragment)

        if not required and intent.subject_area == "project" and intent.entities:
            for entity in intent.entities:
                if entity.type == "project":
                    add("project", entity.value)

        return required

    @staticmethod
    def has_active_project_scope(context: ContextStack) -> bool:
        """True when session has a project from confirmation or prior expense tool."""
        active = context.working_memory.get_active_project()
        if active and active.project_id is not None:
            return True
        if EntityGate.project_confirmed(context):
            return True
        facts = context.working_memory.session_facts
        return bool(
            facts.get("resolved_project_id") or facts.get("last_expense_summary_project_id"),
        )

    @staticmethod
    def intent_requires_entity_confirmation(
        message: str,
        intent: Intent,
        context: ContextStack | None = None,
    ) -> bool:
        """Return True when this turn needs entity discovery/confirmation before KPI tools."""
        if (
            context is not None
            and is_project_expense_follow_up(message)
            and EntityGate.has_active_project_scope(context)
            and not intent.entities
        ):
            return False
        if intent.entities:
            return True
        if EntityGate.infer_required_entities(message, intent, context):
            return True
        query_blob = f"{message} {intent.specific_intent}".lower()
        if intent.subject_area == "project" and intent.primary_action == "fetch_data":
            if is_project_expense_follow_up(message) and context and EntityGate.has_active_project_scope(context):
                return False
            return True
        if looks_like_project_cost_query(query_blob, subject_area=intent.subject_area):
            if is_project_expense_follow_up(message) and context and EntityGate.has_active_project_scope(context):
                return False
            return True
        return False

    async def evaluate(
        self,
        intent: Intent,
        context: ContextStack,
        message: str,
        confirmed_entities: list[ConfirmedEntityRef] | None = None,
    ) -> EntityGateResult:
        """Discover entities and decide whether financial tools may proceed."""
        required = self.infer_required_entities(message, intent, context)
        if not required:
            return EntityGateResult(status="not_required")

        confirmed_map: dict[str, dict[str, Any]] = dict(
            context.working_memory.session_facts.get("confirmed_entities") or {},
        )

        if confirmed_entities:
            for item in confirmed_entities:
                confirmed_map[item.type] = {
                    "id": item.id,
                    "name": item.name or str(item.id),
                }

        pending = [(entity_type, query) for entity_type, query in required if entity_type not in confirmed_map]
        if not pending:
            return EntityGateResult(
                status="confirmed",
                required_types=[item[0] for item in required],
                confirmed=confirmed_map,
            )

        all_matches: list[dict[str, Any]] = []
        query_label = pending[0][1]
        gate_telemetry = {
            "entity_discovery_count": 0,
            "entity_top_confidence": 0.0,
            "entity_strategies_used": [],
            "entity_strategy_that_matched": None,
        }
        using_weak = False

        for entity_type, query in pending:
            matches, discovery, weak = await self._discover(entity_type, query, context)
            gate_telemetry["entity_discovery_count"] = max(
                gate_telemetry["entity_discovery_count"],
                discovery.get("entity_discovery_count", 0),
            )
            gate_telemetry["entity_top_confidence"] = max(
                gate_telemetry["entity_top_confidence"],
                discovery.get("entity_top_confidence", 0.0),
            )
            if discovery.get("entity_strategies_used"):
                gate_telemetry["entity_strategies_used"] = discovery["entity_strategies_used"]
            if discovery.get("entity_strategy_that_matched"):
                gate_telemetry["entity_strategy_that_matched"] = discovery[
                    "entity_strategy_that_matched"
                ]
            if not matches:
                if gate_telemetry["entity_discovery_count"] > 0:
                    logger.warning(
                        "[EntityGate] discovery returned %d raw rows but no usable summaries "
                        "for query=%r — treating as not_found",
                        gate_telemetry["entity_discovery_count"],
                        query,
                    )
                return EntityGateResult(
                    status="not_found",
                    required_types=[item[0] for item in required],
                    query_label=query,
                    **gate_telemetry,
                )
            if weak:
                using_weak = True
            all_matches.extend(matches)

        options = build_entity_options(all_matches)
        return EntityGateResult(
            status="weak_confirmation" if using_weak else "needs_confirmation",
            required_types=[item[0] for item in required],
            matches=all_matches,
            options=options,
            query_label=query_label,
            **gate_telemetry,
        )

    async def _discover(
        self,
        entity_type: str,
        query: str,
        context: ContextStack,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
        if entity_type == "project":
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    result = await self._project_resolver.resolve_project(query, context)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt == 0 and _is_transient_odoo_error(exc):
                        logger.warning(
                            "[EntityGate] transient Odoo error on project discovery (retry): %s",
                            exc,
                        )
                        await asyncio.sleep(0.35)
                        continue
                    logger.warning("[EntityGate] project discovery failed: %s", exc)
                    return [], {"entity_discovery_count": 0, "entity_top_confidence": 0.0}, False
            else:
                logger.warning("[EntityGate] project discovery failed: %s", last_error)
                return [], {"entity_discovery_count": 0, "entity_top_confidence": 0.0}, False

            discovery = {
                "entity_discovery_count": result.raw_discovery_count,
                "entity_top_confidence": result.confidence,
                "entity_strategies_used": list(result.strategies_used),
                "entity_strategy_that_matched": result.winning_strategy,
            }
            match_pool = result.confident_matches
            weak = False
            if not match_pool and result.weak_matches:
                match_pool = result.weak_matches
                weak = True
            if not match_pool and result.raw_discovery_count > 0:
                if result.top_match is not None:
                    match_pool = [result.top_match]
                    weak = result.top_match.confidence < CONFIDENT_CONFIDENCE_MIN
                elif result.confident_matches or result.weak_matches:
                    match_pool = list(result.confident_matches or result.weak_matches)
                    weak = bool(result.weak_matches and not result.confident_matches)

            summaries: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for match in match_pool[:5]:
                entity = match.entity
                entity_id = int(entity.get("id") or 0)
                if entity_id <= 0 or entity_id in seen_ids:
                    continue
                seen_ids.add(entity_id)
                summaries.append(_project_match_summary(entity, match.confidence, weak=weak))
            return summaries, discovery, weak

        if entity_type == "partner":
            try:
                partners = await self._partner_search.search_partners(query)
            except Exception as exc:
                logger.warning("[EntityGate] partner discovery failed: %s", exc)
                return [], {"entity_discovery_count": 0, "entity_top_confidence": 0.0}, False
            summaries = [
                {
                    "id": int(partner.get("id") or 0),
                    "name": partner.get("name"),
                    "entity_type": "partner",
                    "detail": "Company" if partner.get("is_company") else "Contact",
                    "confidence": 0.7,
                }
                for partner in partners
                if int(partner.get("id") or 0) > 0
            ][:5]
            return (
                summaries,
                {
                    "entity_discovery_count": len(summaries),
                    "entity_top_confidence": 0.7 if summaries else 0.0,
                    "entity_strategies_used": ["partner_name_search"],
                    "entity_strategy_that_matched": "partner_name_search" if summaries else None,
                },
                False,
            )

        return [], {"entity_discovery_count": 0, "entity_top_confidence": 0.0}, False

    @staticmethod
    def apply_confirmed_entities(context: ContextStack, confirmed: dict[str, dict[str, Any]]) -> None:
        """Persist confirmed entities into working memory and legacy session facts."""
        context.working_memory.session_facts["confirmed_entities"] = dict(confirmed)
        project = confirmed.get("project")
        if project and project.get("id"):
            context.working_memory.session_facts["resolved_project_id"] = int(project["id"])
            context.working_memory.remember_entity(
                "project",
                {"id": project["id"], "name": project.get("name")},
            )
        partner = confirmed.get("partner")
        if partner and partner.get("id"):
            context.working_memory.session_facts["resolved_partner_id"] = int(partner["id"])
            context.working_memory.remember_entity(
                "partner",
                {"id": partner["id"], "name": partner.get("name")},
            )

    @staticmethod
    def project_confirmed(context: ContextStack) -> bool:
        confirmed = context.working_memory.session_facts.get("confirmed_entities") or {}
        project = confirmed.get("project")
        return bool(project and project.get("id"))

    @staticmethod
    def partner_confirmed(context: ContextStack) -> bool:
        confirmed = context.working_memory.session_facts.get("confirmed_entities") or {}
        partner = confirmed.get("partner")
        return bool(partner and partner.get("id"))


def _format_budget_label(entity: dict[str, Any]) -> str | None:
    for key in ("planned_budget", "budget", "total_budget", "amount_total"):
        raw = entity.get(key)
        if raw in (None, "", 0):
            continue
        try:
            amount = float(raw)
        except (TypeError, ValueError):
            continue
        if amount >= 1_000_000:
            return f"AED {amount / 1_000_000:.1f}M budget"
        if amount >= 1_000:
            return f"AED {amount / 1_000:.0f}K budget"
        return f"AED {amount:,.0f} budget"
    return None


def _partner_label(entity: dict[str, Any]) -> str | None:
    partner = entity.get("partner_id")
    if isinstance(partner, (list, tuple)) and len(partner) >= 2:
        return str(partner[1])
    return None


def _project_match_summary(
    entity: dict[str, Any],
    confidence: float,
    *,
    weak: bool = False,
) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "name": entity.get("name"),
        "entity_type": "project",
        "wo_ref_no": entity.get("wo_ref_no"),
        "detail": entity.get("description") or entity.get("client"),
        "budget_label": _format_budget_label(entity),
        "partner_name": _partner_label(entity),
        "confidence": confidence,
        "weak_match": weak,
    }


def format_entity_confirm_label(match: dict[str, Any]) -> str:
    """Rich single-line label for confirm buttons and prompts."""
    name = str(match.get("name") or "Unknown")
    parts: list[str] = []
    budget = match.get("budget_label")
    if budget:
        parts.append(str(budget))
    wo_ref = match.get("wo_ref_no")
    if wo_ref:
        parts.append(f"WO: {wo_ref}")
    if parts:
        return f"{name} ({', '.join(parts)})"
    return name


def build_entity_not_found_clarification(
    query: str,
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Structured not-found clarification with broadening actions."""
    search_term = meaningful_project_words(query)[0] if meaningful_project_words(query) else query.strip()
    if language == "ar":
        question = (
            f'لم أجد مشروعاً يطابق "{query}" في النظام.\n\n'
            "جرّب:\n"
            '- إملاء مختلف (مثل "Zayed" أو "Zayedia")\n'
            "- رقم أمر العمل\n"
            "- اسم العميل"
        )
    else:
        question = (
            f'I couldn\'t find a project matching "{query}" in the system.\n\n'
            "Try:\n"
            '- A different spelling (e.g., "Zayed", "Zayedia")\n'
            "- The Work Order number (e.g., WO-2025-001)\n"
            '- The client name (e.g., Ministry of Education)\n\n'
            f'Or I can search more broadly — want me to show all projects containing "{search_term}"?'
        )
    return {
        "reason": "entity_not_found",
        "question": question,
        "matches": [],
        "options": [
            {
                "id": "search_broader",
                "label": "Search broader",
                "label_ar": "بحث أوسع",
                "action": "search_broader_entity",
                "search_term": search_term,
            },
            {
                "id": "try_different",
                "label": "Try different name",
                "label_ar": "اسم مختلف",
                "action": "try_different_name",
            },
        ],
    }


def build_entity_options(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build clarification UI options from discovery matches."""
    options: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        entity_type = str(match.get("entity_type") or "project")
        entity_id = match.get("id")
        label = format_entity_confirm_label(match)
        options.append(
            {
                "id": str(entity_id or index),
                "label": label,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": "confirm_entity",
                "is_default": index == 0,
                "weak_match": bool(match.get("weak_match")),
            },
        )
    return options
