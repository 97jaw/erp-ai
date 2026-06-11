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
    extract_project_number_hint,
    extract_suggestion_tokens,
    is_project_expense_follow_up,
    looks_like_project_cost_query,
    meaningful_project_words,
    project_record_matches_number,
    query_mentions_maintenance,
    rank_related_project,
)
from gateway.core.working_memory import ActiveContext

logger = logging.getLogger(__name__)

_TRANSIENT_ODOO_ERRORS = frozenset({"request-sent", "idle", "remotedisconnected"})
_TRANSIENT_DISCOVERY_RETRIES = 3
_TRANSIENT_DISCOVERY_BACKOFF_S = 1.0
_TRANSIENT_ERROR_MARKERS = (
    "502",
    "bad gateway",
    "timeout",
    "timed out",
    "connection",
    "connectionerror",
    "connection reset",
    "connection refused",
    "request-sent",
    "remotedisconnected",
    "service unavailable",
    "503",
    "504",
    "gateway timeout",
)

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
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    message = str(exc).strip().lower()
    if message in _TRANSIENT_ODOO_ERRORS:
        return True
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)


def dedupe_project_ids(project_ids: list[int]) -> list[int]:
    """Return project IDs in order with duplicates removed (fixes P-E1)."""
    seen: set[int] = set()
    deduped: list[int] = []
    for raw in project_ids:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        deduped.append(pid)
    return deduped


def extract_compare_project_queries(intent: Intent) -> list[str]:
    """Distinct project entity values for a compare intent."""
    queries: list[str] = []
    seen: set[str] = set()
    for entity in intent.entities:
        if entity.type != "project":
            continue
        value = entity.value.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(value)
    return queries


def is_compare_project_intent(intent: Intent) -> bool:
    """True when compare mode targets two or more distinct projects."""
    return intent.primary_action == "compare" and len(extract_compare_project_queries(intent)) >= 2


def _project_discovery_query(message: str, entity_value: str) -> str:
    """Use the message hint when it supplies a project number missing from the LLM entity."""
    hint = (extract_project_name_hint(message) or "").strip()
    value = (entity_value or "").strip()
    if not hint:
        return value
    if not value:
        return hint
    num_hint = extract_project_number_hint(hint)
    num_value = extract_project_number_hint(value)
    if num_hint and not num_value:
        return hint
    return value


def _number_hint_from_query_and_message(query: str, message: str) -> str | None:
    """Extract villa/project number from discovery query or full user message."""
    number = extract_project_number_hint(query)
    if number:
        return number
    message_hint = extract_project_name_hint(message) or ""
    return extract_project_number_hint(message_hint)


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
    "transient_error",
]

ENTITY_BOUND_FINANCIAL_TOOLS: frozenset[str] = frozenset(
    {
        "get_project_expenses",
        "get_project_financial_data",
        "get_project_cost_categories",
        "get_project_expense_summary",
        "get_project_expense_breakdown",
        "get_project_profile",
        "get_project_records",
        "get_project_activity",
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
    "get_project_profile": ["project"],
    "get_project_records": ["project"],
    "get_project_activity": ["project"],
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
    compare_project_ids: list[int] = field(default_factory=list)
    compare_resolved_projects: list[dict[str, Any]] = field(default_factory=list)
    compare_pending_query: str = ""
    entity_near_miss: bool = False


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
        if intent.subject_area == "project_attribute":
            return intent
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
                value = entity.value
                if entity_type == "project":
                    value = _project_discovery_query(message, entity.value)
                add(entity_type, value)

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
                    add("project", _project_discovery_query(message, entity.value))

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
        if intent.subject_area == "project_attribute":
            return False
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
        if is_compare_project_intent(intent):
            return await self._evaluate_compare(
                intent,
                context,
                message,
                confirmed_entities,
            )

        required = self.infer_required_entities(message, intent, context)
        if not required:
            return EntityGateResult(status="not_required")

        confirmed_map: dict[str, dict[str, Any]] = dict(
            context.working_memory.session_facts.get("confirmed_entities") or {},
        )

        # Types explicitly confirmed by the user this turn (clarification click).
        # These are authoritative: the user may have picked a near-miss candidate
        # whose name does NOT match the original query text (e.g. typed "Villa 37",
        # picked "Villa Maintenance No. 34") — never re-validate them against the
        # message hint or we loop back into the same clarification.
        user_confirmed_types: set[str] = set()
        if confirmed_entities:
            for item in confirmed_entities:
                confirmed_map[item.type] = {
                    "id": item.id,
                    "name": item.name or str(item.id),
                }
                user_confirmed_types.add(item.type)

        active = context.working_memory.get_active_project()
        if active and active.confirmed and active.project_id:
            project_pending = [(entity_type, query) for entity_type, query in required if entity_type == "project"]
            entity_hint = self._extract_entity_hint(intent, message)
            if project_pending and all(
                self._matches_active(query, active) for _, query in project_pending
            ) and self._matches_active(entity_hint, active):
                logger.info(
                    "[EntityGate] Skipping confirm — %s already confirmed this session",
                    active.project_name,
                )
                confirmed_map["project"] = {
                    "id": int(active.project_id),
                    "name": active.project_name or str(active.project_id),
                }
                return EntityGateResult(
                    status="confirmed",
                    required_types=[item[0] for item in required],
                    confirmed=confirmed_map,
                )

        pending: list[tuple[str, str]] = []
        entity_hint = self._extract_entity_hint(intent, message)
        for entity_type, query in required:
            if entity_type not in confirmed_map:
                pending.append((entity_type, query))
                continue
            if entity_type in user_confirmed_types:
                continue
            if entity_type == "project":
                confirmed_project = confirmed_map["project"]
                confirmed_active = ActiveContext(
                    project_id=int(confirmed_project["id"]),
                    project_name=str(confirmed_project.get("name") or ""),
                    confirmed=True,
                )
                if not self._matches_active(query, confirmed_active) or not self._matches_active(
                    entity_hint,
                    confirmed_active,
                ):
                    pending.append((entity_type, query))
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
        entity_near_miss = False

        for entity_type, query in pending:
            matches, discovery, weak, transient_failed = await self._discover(
                entity_type,
                query,
                context,
                message=message,
            )
            if discovery.get("entity_near_miss"):
                entity_near_miss = True
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
            if transient_failed:
                return EntityGateResult(
                    status="transient_error",
                    required_types=[item[0] for item in required],
                    query_label=query,
                    **gate_telemetry,
                )
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
                    entity_near_miss=entity_near_miss,
                    **gate_telemetry,
                )
            if weak:
                using_weak = True
            all_matches.extend(matches)

        auto_confirmed = self._auto_confirm_project_match(
            all_matches,
            message=message,
            context=context,
            using_weak=using_weak,
        )
        if auto_confirmed is not None:
            confirmed_map["project"] = {
                "id": int(auto_confirmed.get("id") or 0),
                "name": str(auto_confirmed.get("name") or auto_confirmed.get("id")),
            }
            logger.info(
                "[EntityGate] Auto-confirmed project %s (id=%s) for query %r",
                confirmed_map["project"]["name"],
                confirmed_map["project"]["id"],
                query_label,
            )
            return EntityGateResult(
                status="confirmed",
                required_types=[item[0] for item in required],
                confirmed=confirmed_map,
                query_label=query_label,
                **gate_telemetry,
            )

        options = build_entity_options(all_matches)
        return EntityGateResult(
            status="weak_confirmation" if using_weak else "needs_confirmation",
            required_types=[item[0] for item in required],
            matches=all_matches,
            options=options,
            query_label=query_label,
            entity_near_miss=entity_near_miss,
            **gate_telemetry,
        )

    async def _evaluate_compare(
        self,
        intent: Intent,
        context: ContextStack,
        message: str,
        confirmed_entities: list[ConfirmedEntityRef] | None,
    ) -> EntityGateResult:
        """Resolve two or more project entities independently for compare mode."""
        del message
        queries = extract_compare_project_queries(intent)
        facts = context.working_memory.session_facts
        resolved: list[dict[str, Any]] = list(facts.get("compare_resolved_projects") or [])
        gate_telemetry = {
            "entity_discovery_count": 0,
            "entity_top_confidence": 0.0,
            "entity_strategies_used": [],
            "entity_strategy_that_matched": None,
        }

        project_confirms = [
            item for item in (confirmed_entities or []) if item.type == "project"
        ]
        if len(project_confirms) >= 2:
            resolved = []
            for index, item in enumerate(project_confirms[: len(queries)]):
                query = queries[index] if index < len(queries) else (item.name or str(item.id))
                resolved = self._upsert_compare_resolved(
                    resolved,
                    query=query,
                    entity_id=int(item.id),
                    name=item.name or str(item.id),
                )
        elif len(project_confirms) == 1:
            pending_query = str(facts.get("compare_pending_query") or "")
            if not pending_query:
                resolved_queries = {item["query"].lower() for item in resolved}
                pending_query = next(
                    (query for query in queries if query.lower() not in resolved_queries),
                    queries[-1],
                )
            item = project_confirms[0]
            resolved = self._upsert_compare_resolved(
                resolved,
                query=pending_query,
                entity_id=int(item.id),
                name=item.name or str(item.id),
            )

        resolved_by_query = {item["query"].lower(): item for item in resolved}
        pending_matches: list[dict[str, Any]] = []
        pending_query = ""
        pending_weak = False

        for query in queries:
            if query.lower() in resolved_by_query:
                continue

            resolution, transient_failed = await self._resolve_project_for_compare(query, context)
            if transient_failed:
                return EntityGateResult(
                    status="transient_error",
                    required_types=["project", "project"],
                    query_label=query,
                    **gate_telemetry,
                )
            if resolution is None:
                return EntityGateResult(
                    status="not_found",
                    required_types=["project", "project"],
                    query_label=query,
                    **gate_telemetry,
                )

            gate_telemetry["entity_discovery_count"] = max(
                gate_telemetry["entity_discovery_count"],
                resolution.raw_discovery_count,
            )
            gate_telemetry["entity_top_confidence"] = max(
                gate_telemetry["entity_top_confidence"],
                resolution.confidence,
            )
            if resolution.strategies_used:
                gate_telemetry["entity_strategies_used"] = resolution.strategies_used
            if resolution.winning_strategy:
                gate_telemetry["entity_strategy_that_matched"] = resolution.winning_strategy

            if resolution.raw_discovery_count == 0 and not resolution.top_match:
                return EntityGateResult(
                    status="not_found",
                    required_types=["project", "project"],
                    query_label=query,
                    **gate_telemetry,
                )

            if self._compare_slot_is_clear(resolution):
                top = resolution.top_match or resolution.confident_matches[0]
                resolved = self._upsert_compare_resolved(
                    resolved,
                    query=query,
                    entity_id=int(top.entity.get("id") or 0),
                    name=str(top.entity.get("name") or query),
                )
                resolved_by_query = {item["query"].lower(): item for item in resolved}
                continue

            match_pool = resolution.confident_matches or resolution.weak_matches
            if not match_pool and resolution.top_match is not None:
                match_pool = [resolution.top_match]
            weak = bool(
                resolution.weak_matches
                and not resolution.confident_matches
            ) or resolution.ambiguity_level == "weak_matches"
            pending_matches = [
                _project_match_summary(
                    match.entity,
                    match.confidence,
                    weak=weak or match.confidence < CONFIDENT_CONFIDENCE_MIN,
                )
                for match in match_pool[:5]
            ]
            if not pending_matches:
                return EntityGateResult(
                    status="not_found",
                    required_types=["project", "project"],
                    query_label=query,
                    **gate_telemetry,
                )

            pending_query = query
            pending_weak = weak
            break

        ordered_resolved = self._order_compare_resolved(resolved, queries)
        compare_ids = dedupe_project_ids([int(item["id"]) for item in ordered_resolved])

        if len(ordered_resolved) >= 2 and len(compare_ids) >= 2:
            compare_ids = compare_ids[:2]
            ordered_resolved = ordered_resolved[:2]
            self.apply_compare_projects(context, ordered_resolved, compare_ids)
            logger.info(
                "[EntityGate] Compare mode confirmed projects %s",
                compare_ids,
            )
            return EntityGateResult(
                status="confirmed",
                required_types=["project", "project"],
                confirmed={"compare_projects": ordered_resolved},
                compare_project_ids=compare_ids,
                compare_resolved_projects=ordered_resolved,
                query_label=queries[0],
                **gate_telemetry,
            )

        if pending_query and pending_matches:
            facts["compare_resolved_projects"] = ordered_resolved
            facts["compare_pending_query"] = pending_query
            options = build_entity_options(pending_matches)
            resolved_names = ", ".join(
                str(item.get("name") or item.get("id")) for item in ordered_resolved
            )
            if ordered_resolved:
                logger.info(
                    "[EntityGate] Compare mode resolved %s; awaiting confirmation for %r",
                    resolved_names,
                    pending_query,
                )
            return EntityGateResult(
                status="weak_confirmation" if pending_weak else "needs_confirmation",
                required_types=["project", "project"],
                matches=pending_matches,
                options=options,
                compare_resolved_projects=ordered_resolved,
                compare_pending_query=pending_query,
                query_label=pending_query,
                **gate_telemetry,
            )

        if len(ordered_resolved) >= 2 and len(compare_ids) < 2:
            return EntityGateResult(
                status="needs_confirmation",
                required_types=["project", "project"],
                query_label=queries[-1],
                compare_resolved_projects=ordered_resolved,
                compare_pending_query=queries[-1],
                **gate_telemetry,
            )

        return EntityGateResult(
            status="not_found",
            required_types=["project", "project"],
            query_label=queries[0],
            **gate_telemetry,
        )

    async def _resolve_project_for_compare(
        self,
        query: str,
        context: ContextStack,
    ) -> tuple[Any | None, bool]:
        """Resolve one compare slot; return (result, transient_failed)."""
        last_exc: Exception | None = None
        for attempt in range(_TRANSIENT_DISCOVERY_RETRIES):
            try:
                return await self._project_resolver.resolve_project(query, context), False
            except Exception as exc:
                last_exc = exc
                if not _is_transient_odoo_error(exc):
                    logger.warning("[EntityGate] compare project discovery failed: %s", exc)
                    return None, False
                if attempt < _TRANSIENT_DISCOVERY_RETRIES - 1:
                    logger.warning(
                        "[EntityGate] transient Odoo error on compare discovery "
                        "(retry %d/%d): %s",
                        attempt + 1,
                        _TRANSIENT_DISCOVERY_RETRIES,
                        exc,
                    )
                    await asyncio.sleep(_TRANSIENT_DISCOVERY_BACKOFF_S)
                    continue
                logger.warning(
                    "[EntityGate] transient Odoo error on compare discovery "
                    "(exhausted retries): %s",
                    exc,
                )
                return None, True
        logger.warning("[EntityGate] compare project discovery failed: %s", last_exc)
        return None, False

    @staticmethod
    def _compare_slot_is_clear(resolution: Any) -> bool:
        """True when one project clearly wins for a compare slot."""
        if resolution.top_match is None:
            return False
        if resolution.ambiguity_level in {"unambiguous", "clear_winner"}:
            return resolution.top_match.confidence >= CONFIDENT_CONFIDENCE_MIN
        if len(resolution.confident_matches) == 1:
            return resolution.confident_matches[0].confidence >= CONFIDENT_CONFIDENCE_MIN
        if len(resolution.confident_matches) >= 2:
            top = resolution.confident_matches[0]
            second = resolution.confident_matches[1]
            return (
                top.confidence >= CONFIDENT_CONFIDENCE_MIN
                and top.confidence - second.confidence >= 0.2
            )
        return False

    @staticmethod
    def _upsert_compare_resolved(
        resolved: list[dict[str, Any]],
        *,
        query: str,
        entity_id: int,
        name: str,
    ) -> list[dict[str, Any]]:
        updated = [
            item for item in resolved if str(item.get("query", "")).lower() != query.lower()
        ]
        updated.append({"query": query, "id": entity_id, "name": name})
        return updated

    @staticmethod
    def _order_compare_resolved(
        resolved: list[dict[str, Any]],
        queries: list[str],
    ) -> list[dict[str, Any]]:
        by_query = {item["query"].lower(): item for item in resolved}
        ordered: list[dict[str, Any]] = []
        for query in queries:
            item = by_query.get(query.lower())
            if item is not None:
                ordered.append(item)
        for item in resolved:
            if item not in ordered:
                ordered.append(item)
        return ordered

    @staticmethod
    def apply_compare_projects(
        context: ContextStack,
        resolved_projects: list[dict[str, Any]],
        project_ids: list[int],
    ) -> None:
        """Persist two distinct project IDs for compare_project_expenses."""
        compare_ids = dedupe_project_ids(project_ids)
        facts = context.working_memory.session_facts
        facts["compare_resolved_projects"] = list(resolved_projects)
        facts["compare_project_ids"] = compare_ids
        facts["resolved_project_ids"] = compare_ids
        facts.pop("compare_pending_query", None)
        facts["confirmed_entities"] = {
            "compare_projects": [
                {"id": item["id"], "name": item.get("name")}
                for item in resolved_projects[:2]
            ],
        }
        if compare_ids:
            first = resolved_projects[0] if resolved_projects else {"id": compare_ids[0]}
            facts["resolved_project_id"] = int(compare_ids[0])
            context.working_memory.remember_entity(
                "project",
                {"id": first.get("id"), "name": first.get("name")},
            )

    @staticmethod
    def _auto_confirm_project_match(
        matches: list[dict[str, Any]],
        *,
        message: str,
        context: ContextStack,
        using_weak: bool,
    ) -> dict[str, Any] | None:
        """Return the project summary to auto-confirm for numbered villa/project queries."""
        if using_weak or not matches:
            return None

        number_hint = _number_hint_from_query_and_message(message, message)
        if not number_hint:
            return None

        numbered = [
            match
            for match in matches
            if project_record_matches_number(match, number_hint)
        ]
        if len(numbered) == 1:
            top = numbered[0]
            if float(top.get("confidence") or 0.0) >= CONFIDENT_CONFIDENCE_MIN:
                return top

        if context.user.assumption_level() == "aggressive" and len(matches) >= 2:
            top = matches[0]
            second = matches[1]
            top_conf = float(top.get("confidence") or 0.0)
            second_conf = float(second.get("confidence") or 0.0)
            if (
                top_conf >= 0.92
                and top_conf - second_conf >= 0.2
                and project_record_matches_number(top, number_hint)
            ):
                return top

        return None

    async def _discover_related_projects(
        self,
        query: str,
        message: str,
        context: ContextStack,
        *,
        pool_matches: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Token-based broad search when exact entity match fails."""
        del context
        hint = extract_project_name_hint(message) or ""
        token_source = f"{query} {hint}".strip()
        tokens = extract_suggestion_tokens(token_source)
        maintenance_query = query_mentions_maintenance(query) or query_mentions_maintenance(message)

        if pool_matches:
            pool_entities = [
                match.entity if hasattr(match, "entity") else match for match in pool_matches
            ]
            if maintenance_query:
                maintenance_entities = [
                    entity
                    for entity in pool_entities
                    if "maintenance" in str(entity.get("name") or "").lower()
                ]
                pool_entities = maintenance_entities
            summaries = _rank_related_summaries(
                pool_entities,
                tokens,
                maintenance_query=maintenance_query,
            )
            if summaries:
                return summaries

        if not tokens:
            return []

        search = self._project_resolver._search
        candidates_by_id: dict[int, dict[str, Any]] = {}

        if maintenance_query and "villa" in tokens:
            try:
                results = await search.search_projects(
                    [["name", "ilike", "Villa Maintenance"]],
                    limit=30,
                )
            except Exception as exc:
                logger.warning(
                    "[EntityGate] villa maintenance fast-path search failed: %s",
                    exc,
                )
            else:
                for project in results:
                    project_id = int(project.get("id") or 0)
                    if project_id > 0:
                        candidates_by_id[project_id] = project
        else:
            search_tokens = tokens[:2]
            if len(search_tokens) >= 2:
                domain: list[Any] = [["name", "ilike", token] for token in search_tokens]
                domain = ["&"] + domain
            else:
                domain = [["name", "ilike", search_tokens[0]]]
            try:
                results = await search.search_projects(domain, limit=30)
            except Exception as exc:
                logger.warning(
                    "[EntityGate] related project AND search failed for %r: %s",
                    search_tokens,
                    exc,
                )
            else:
                for project in results:
                    project_id = int(project.get("id") or 0)
                    if project_id > 0:
                        candidates_by_id[project_id] = project

        if not candidates_by_id:
            return []

        return _rank_related_summaries(
            list(candidates_by_id.values()),
            tokens,
            maintenance_query=maintenance_query,
        )

    async def _try_related_project_fallback(
        self,
        query: str,
        message: str,
        context: ContextStack,
        discovery: dict[str, Any],
        *,
        pool_matches: list[Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], bool, bool] | None:
        """Return related-project summaries when exact discovery finds nothing."""
        related = await self._discover_related_projects(
            query,
            message,
            context,
            pool_matches=pool_matches,
        )
        if not related:
            return None
        updated_discovery = dict(discovery)
        updated_discovery["entity_near_miss"] = True
        updated_discovery["entity_discovery_count"] = max(
            updated_discovery.get("entity_discovery_count", 0),
            len(related),
        )
        logger.info(
            "[EntityGate] Exact match failed for %r — suggesting %d related projects",
            query,
            len(related),
        )
        return related, updated_discovery, True, False

    async def _discover(
        self,
        entity_type: str,
        query: str,
        context: ContextStack,
        *,
        message: str = "",
    ) -> tuple[list[dict[str, Any]], dict[str, Any], bool, bool]:
        empty_discovery: dict[str, Any] = {
            "entity_discovery_count": 0,
            "entity_top_confidence": 0.0,
        }

        if entity_type == "project":
            result = None
            for attempt in range(_TRANSIENT_DISCOVERY_RETRIES):
                try:
                    result = await self._project_resolver.resolve_project(query, context)
                    break
                except Exception as exc:
                    if not _is_transient_odoo_error(exc):
                        logger.warning("[EntityGate] project discovery failed: %s", exc)
                        return [], empty_discovery, False, False
                    if attempt < _TRANSIENT_DISCOVERY_RETRIES - 1:
                        logger.warning(
                            "[EntityGate] transient Odoo error on project discovery "
                            "(retry %d/%d): %s",
                            attempt + 1,
                            _TRANSIENT_DISCOVERY_RETRIES,
                            exc,
                        )
                        await asyncio.sleep(_TRANSIENT_DISCOVERY_BACKOFF_S)
                        continue
                    logger.warning(
                        "[EntityGate] transient Odoo error on project discovery "
                        "(exhausted retries): %s",
                        exc,
                    )
                    return [], empty_discovery, False, True

            if result is None:
                return [], empty_discovery, False, True

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

            pre_filter_pool = list(match_pool)

            number_hint = _number_hint_from_query_and_message(query, message)
            if number_hint and match_pool:
                numbered_matches = [
                    match
                    for match in match_pool
                    if project_record_matches_number(match.entity, number_hint)
                ]
                if query_mentions_maintenance(query) or query_mentions_maintenance(message):
                    maintenance_numbered = [
                        match
                        for match in numbered_matches
                        if "maintenance" in str(match.entity.get("name") or "").lower()
                    ]
                    if maintenance_numbered:
                        numbered_matches = maintenance_numbered
                    elif numbered_matches:
                        logger.info(
                            "[EntityGate] Query %r requested maintenance number %s "
                            "but no maintenance project name contains it — near_miss fallback",
                            query,
                            number_hint,
                        )
                        fallback = await self._try_related_project_fallback(
                            query,
                            message,
                            context,
                            discovery,
                            pool_matches=pre_filter_pool,
                        )
                        if fallback is not None:
                            return fallback
                        return [], discovery, False, False
                if numbered_matches:
                    match_pool = numbered_matches
                else:
                    logger.info(
                        "[EntityGate] Query %r requested villa/project number %s "
                        "but no discovery match contains it — near_miss fallback",
                        query,
                        number_hint,
                    )
                    fallback = await self._try_related_project_fallback(
                        query,
                        message,
                        context,
                        discovery,
                        pool_matches=pre_filter_pool,
                    )
                    if fallback is not None:
                        return fallback
                    return [], discovery, False, False

            summaries: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for match in match_pool[:5]:
                entity = match.entity
                entity_id = int(entity.get("id") or 0)
                if entity_id <= 0 or entity_id in seen_ids:
                    continue
                seen_ids.add(entity_id)
                summaries.append(_project_match_summary(entity, match.confidence, weak=weak))

            if not summaries:
                fallback = await self._try_related_project_fallback(
                    query,
                    message,
                    context,
                    discovery,
                    pool_matches=pre_filter_pool,
                )
                if fallback is not None:
                    return fallback

            return summaries, discovery, weak, False

        if entity_type == "partner":
            partners: list[dict[str, Any]] | None = None
            for attempt in range(_TRANSIENT_DISCOVERY_RETRIES):
                try:
                    partners = await self._partner_search.search_partners(query)
                    break
                except Exception as exc:
                    if not _is_transient_odoo_error(exc):
                        logger.warning("[EntityGate] partner discovery failed: %s", exc)
                        return [], empty_discovery, False, False
                    if attempt < _TRANSIENT_DISCOVERY_RETRIES - 1:
                        logger.warning(
                            "[EntityGate] transient Odoo error on partner discovery "
                            "(retry %d/%d): %s",
                            attempt + 1,
                            _TRANSIENT_DISCOVERY_RETRIES,
                            exc,
                        )
                        await asyncio.sleep(_TRANSIENT_DISCOVERY_BACKOFF_S)
                        continue
                    logger.warning(
                        "[EntityGate] transient Odoo error on partner discovery "
                        "(exhausted retries): %s",
                        exc,
                    )
                    return [], empty_discovery, False, True

            if partners is None:
                return [], empty_discovery, False, True
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
                False,
            )

        return [], empty_discovery, False, False

    @staticmethod
    def _extract_entity_hint(intent: Intent, message: str) -> str:
        for entity in intent.entities:
            if entity.type == "project":
                return entity.value
        hint = extract_project_name_hint(message)
        return hint or ""

    @staticmethod
    def _matches_active(hint: str, active: ActiveContext) -> bool:
        if not hint:
            return True
        hint_lower = hint.strip().lower()
        if hint_lower == str(active.project_id):
            return True
        active_name = (active.project_name or "").lower()
        if active_name and (
            hint_lower in active_name
            or active_name in hint_lower
        ):
            return True
        hint_tokens = [token for token in hint_lower.replace("-", " ").split() if token]
        if hint_tokens and active_name and all(token in active_name for token in hint_tokens):
            return True
        return False

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
    def compare_projects_confirmed(context: ContextStack) -> bool:
        """True when compare mode has two distinct resolved project IDs."""
        facts = context.working_memory.session_facts
        compare_ids = facts.get("compare_project_ids") or []
        return len(dedupe_project_ids([int(value) for value in compare_ids])) >= 2

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


def _rank_related_summaries(
    entities: list[dict[str, Any]],
    tokens: list[str],
    *,
    maintenance_query: bool,
) -> list[dict[str, Any]]:
    """Rank resolver or search candidates locally without extra Odoo calls."""
    ranked = sorted(
        entities,
        key=lambda project: (
            -rank_related_project(project, tokens, maintenance_query=maintenance_query),
            str(project.get("name") or "").lower(),
        ),
    )
    summaries: list[dict[str, Any]] = []
    for project in ranked:
        score = rank_related_project(project, tokens, maintenance_query=maintenance_query)
        if score < 0:
            continue
        summaries.append(
            _project_match_summary(project, min(0.55, 0.35 + score * 0.1), weak=True),
        )
        if len(summaries) >= 5:
            break
    return summaries


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


def build_entity_transient_error_clarification(
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Structured clarification when Odoo discovery fails due to transient infra errors."""
    if language == "ar":
        question = (
            "أواجه صعوبة في الوصول إلى قاعدة البيانات الآن. "
            "يرجى المحاولة مرة أخرى بعد لحظة."
        )
    else:
        question = (
            "I'm having trouble reaching the database right now. "
            "Please try again in a moment."
        )
    return {
        "reason": "transient_error",
        "question": question,
        "matches": [],
        "options": [],
    }


def build_entity_near_miss_clarification(
    query: str,
    options: list[dict[str, Any]],
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Clarification when exact match failed but related projects were found."""
    if language == "ar":
        question = (
            f'لم أجد تطابقاً دقيقاً لـ "{query}" في Odoo.\n\n'
            "إليك أقرب المشاريع بالاسم — أيها تقصد؟"
        )
    else:
        question = (
            f'I couldn\'t find an exact match for **"{query}"** in Odoo.\n\n'
            "Here are the closest projects by name — which one did you mean?"
        )
    return {
        "reason": "entity_near_miss",
        "question": question,
        "matches": options,
        "options": options,
    }


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
