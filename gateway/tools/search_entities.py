"""Entity search tool for discovery-style queries (Phase F3)."""

from __future__ import annotations

import asyncio
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.entity_gate import _project_match_summary
from gateway.core.entity_resolver import CONFIDENT_CONFIDENCE_MIN, EntityResolver, OdooProjectSearch


def minimal_search_context(*, user_message: str = "") -> ContextStack:
    """Build a lightweight context for standalone search_entities tool calls."""
    from gateway.core.business_context import BusinessContext
    from gateway.core.capability_manifest import CAPABILITY_MANIFEST
    from gateway.core.context_stack import ContextStack, ConversationContext, QualityTargets
    from gateway.core.temporal_context import TemporalContext
    from gateway.core.user_context import UserContext
    from gateway.core.working_memory import WorkingMemory

    return ContextStack(
        user=UserContext(
            user_id=0,
            name="Agent",
            file_id=None,
            primary_role="super_admin",
            level=100,
            permissions={"data.all_projects"},
            primary_department="General",
            departments=["General"],
            preferred_language="en",
            preferred_currency="AED",
            default_date_range="last_3_months",
            response_style="brief",
            last_login=None,
            typical_queries=[],
        ),
        conversation=ConversationContext(session_id=None, message=user_message),
        capability_manifest=CAPABILITY_MANIFEST,
        working_memory=WorkingMemory(),
        business_context=BusinessContext(),
        temporal_context=TemporalContext.build(),
        quality_targets=QualityTargets(),
    )


async def execute_search_entities(
    adapter: Any,
    tool_input: dict[str, Any],
    context: ContextStack,
    *,
    project_resolver: EntityResolver | None = None,
) -> dict[str, Any]:
    """Search Odoo for entity candidates matching a natural-language query."""
    entity_type = str(tool_input.get("entity_type") or "project")
    query = str(tool_input.get("query") or "").strip()
    limit = max(1, min(int(tool_input.get("limit") or 10), 20))
    min_confidence = float(tool_input.get("min_confidence") or 0.3)

    if not query:
        return {
            "status": "error",
            "error": "missing_query",
            "message": "search_entities requires a non-empty query.",
        }

    if entity_type != "project":
        return {
            "status": "error",
            "error": "unsupported_entity_type",
            "message": f"Entity type {entity_type!r} is not supported yet.",
        }

    if query.isdigit():
        project_id = int(query)
        records = await asyncio.to_thread(
            adapter.safe_search_read,
            "project.project",
            [["id", "=", project_id]],
            ["id", "name", "wo_ref_no", "description", "partner_id"],
            limit=1,
        )
        if records:
            candidate = _project_match_summary(records[0], confidence=1.0)
            return {
                "status": "success",
                "_source": "search_entities",
                "entity_type": entity_type,
                "query": query,
                "total_matches": 1,
                "candidates": [candidate],
                "top_confidence": 1.0,
            }
        return {
            "status": "success",
            "_source": "search_entities",
            "entity_type": entity_type,
            "query": query,
            "total_matches": 0,
            "candidates": [],
            "message": f"No project with id {project_id}.",
        }

    resolver = project_resolver or EntityResolver(OdooProjectSearch(adapter))
    result = await resolver.resolve_project(query, context, min_confidence=min_confidence)

    match_pool = list(result.confident_matches)
    using_weak = False
    if not match_pool and result.weak_matches:
        match_pool = list(result.weak_matches)
        using_weak = True
    if not match_pool and result.top_match is not None:
        match_pool = [result.top_match]
        using_weak = result.top_match.confidence < CONFIDENT_CONFIDENCE_MIN

    candidates: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for match in match_pool[:limit]:
        entity = match.entity
        entity_id = int(entity.get("id") or 0)
        if entity_id <= 0 or entity_id in seen_ids:
            continue
        seen_ids.add(entity_id)
        candidates.append(
            _project_match_summary(entity, match.confidence, weak=using_weak),
        )

    if not candidates:
        return {
            "status": "success",
            "_source": "search_entities",
            "entity_type": entity_type,
            "query": query,
            "total_matches": 0,
            "candidates": [],
            "message": f"No {entity_type}s found matching {query!r}.",
        }

    return {
        "status": "success",
        "_source": "search_entities",
        "entity_type": entity_type,
        "query": query,
        "total_matches": len(candidates),
        "candidates": candidates,
        "discovery_count": result.raw_discovery_count,
        "top_confidence": result.confidence,
    }
