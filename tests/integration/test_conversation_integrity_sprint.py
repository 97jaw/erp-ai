"""Phase F6 — replay the 2026-06-09 Villa 48 incident sequence (integration)."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.entity_gate import ConfirmedEntityRef
from gateway.core.entity_resolver import EntityResolver
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.result_synthesizer import ResultSynthesizer
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from gateway.session_scope import SessionScopeStore
from tests.core.test_entity_resolver import MockProjectSearch
from tests.core.test_execution_orchestrator import MockToolExecutor
from tests.integration.test_intelligent_handler import (
    StubProactiveIntelligence,
    _stack_for_user,
    _super_admin,
)


VILLA_48_ID = 3288
AL_MUSHRIF_ID = 7711

INCIDENT_CATALOG: list[dict[str, Any]] = [
    {
        "id": VILLA_48_ID,
        "name": "Villa Maintenance No. 48",
        "wo_ref_no": "WO-VM-48",
        "description": "Villa maintenance contract",
    },
    {
        "id": 501,
        "name": "General Maintenance Contract A",
        "wo_ref_no": "WO-GM-A",
        "description": "General maintenance work contract",
    },
    {
        "id": 502,
        "name": "General Maintenance Work - Block B",
        "wo_ref_no": "WO-GM-B",
        "description": "General maintenance work block B",
    },
    {
        "id": AL_MUSHRIF_ID,
        "name": "General Maintenance Work - Al Mushrif",
        "wo_ref_no": "WO-GM-MUSHRIF",
        "description": "General maintenance work Al Mushrif district",
    },
]


class MappedIntentAnalyzer:
    """Map query substrings to intents (stable across confirmation retries)."""

    def __init__(self, mapping: list[tuple[str, Intent]], *, fallback: Intent | None = None) -> None:
        self._mapping = mapping
        self._fallback = fallback or mapping[-1][1]

    async def analyze(self, query: str, context: Any) -> Intent:
        del context
        lowered = query.lower()
        for needle, intent in self._mapping:
            if needle.lower() in lowered:
                return intent
        return self._fallback


class TrackingToolExecutor(MockToolExecutor):
    """Record project IDs passed to expense tools."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.expense_project_ids: list[int | None] = []

    async def execute(self, tool: str, tool_input: dict[str, Any], context: Any) -> Any:
        if tool in {
            "get_project_expense_summary",
            "get_project_expenses",
            "get_project_expense_breakdown",
        }:
            project_id = tool_input.get("project_id")
            self.expense_project_ids.append(int(project_id) if project_id is not None else None)
        return await super().execute(tool, tool_input, context)


def _expense_summary(project_id: int, project_name: str) -> dict[str, Any]:
    return {
        "status": "success",
        "project_id": project_id,
        "project_name": project_name,
        "currency": "AED",
        "wo_amount": 200_000,
        "total_expenses": 50_000,
        "spend_percent_of_wo": 25.0,
        "top_expenses": [{"name": "Labor", "amount": 30_000, "percent": 60.0}],
        "expense_lines": [{"label": "Labor", "amount": 30_000}],
        "variance_amount": 150_000,
        "is_over_budget": False,
        "_source": "project_expense_summary",
    }


def _search_candidates() -> dict[str, Any]:
    return {
        "status": "success",
        "_source": "search_entities",
        "query": "General maintenance work",
        "total_matches": 2,
        "candidates": [
            {
                "id": 501,
                "name": "General Maintenance Contract A",
                "entity_type": "project",
                "wo_ref_no": "WO-GM-A",
            },
            {
                "id": 502,
                "name": "General Maintenance Work - Block B",
                "entity_type": "project",
                "wo_ref_no": "WO-GM-B",
            },
        ],
    }


def _incident_intents() -> list[Intent]:
    return [
        Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="Villa Maintenance No. 48 expense for this year",
            entities=[
                EntityReference(type="project", value="Villa Maintenance No. 48", confidence=0.9),
            ],
            estimated_complexity="simple",
        ),
        Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="General maintenance work need expense report",
            entities=[
                EntityReference(type="project", value="General maintenance work", confidence=0.85),
            ],
            estimated_complexity="simple",
        ),
        Intent(
            primary_action="search_entity",
            subject_area="project",
            specific_intent="now General maintenance work",
            entities=[
                EntityReference(type="project", value="General maintenance work", confidence=0.9),
            ],
            estimated_complexity="simple",
        ),
        Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="give General maintenance work need expense report",
            entities=[
                EntityReference(type="project", value="General maintenance work", confidence=0.85),
            ],
            estimated_complexity="simple",
        ),
        Intent(
            primary_action="fetch_data",
            subject_area="project",
            specific_intent="General maintenance work - Al Mushrif need expense report",
            entities=[
                EntityReference(
                    type="project",
                    value="General maintenance work - Al Mushrif",
                    confidence=0.9,
                ),
            ],
            estimated_complexity="simple",
        ),
    ]


def _incident_intent_mapping() -> list[tuple[str, Intent]]:
    intents = _incident_intents()
    return [
        ("villa maintenance no. 48", intents[0]),
        ("general maintenance work need expense report", intents[1]),
        ("now general maintenance work", intents[2]),
        ("give general maintenance work", intents[3]),
        ("al mushrif", intents[4]),
    ]


def _build_incident_handler(executor: TrackingToolExecutor) -> IntelligentQueryHandler:
    return IntelligentQueryHandler(
        context_builder=ContextStackBuilder(),
        intent_analyzer=MappedIntentAnalyzer(_incident_intent_mapping()),
        entity_resolver=EntityResolver(MockProjectSearch(INCIDENT_CATALOG)),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
        synthesizer=ResultSynthesizer(),
    )


@pytest.fixture(autouse=True)
def _clear_session_scope() -> None:
    SessionScopeStore._memory.clear()


@pytest.mark.asyncio
async def test_incident_five_turn_sequence() -> None:
    """Replay bug-report queries: Villa → general maintenance → topic shift → Al Mushrif."""
    session_id = "incident-2026-06-09-replay"
    user = _super_admin()
    executor = TrackingToolExecutor(
        responses={
            ("get_project_expense_summary", 1): _expense_summary(
                VILLA_48_ID,
                "Villa Maintenance No. 48",
            ),
            ("get_project_expense_summary", 2): _expense_summary(
                AL_MUSHRIF_ID,
                "General Maintenance Work - Al Mushrif",
            ),
            ("search_entities", 1): _search_candidates(),
        },
    )
    handler = _build_incident_handler(executor)

    turn1_query = "Villa Maintenance No. 48 expense for this year"
    turn1_first = await handler.handle(
        turn1_query,
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
    )
    assert turn1_first.awaiting_clarification
    assert turn1_first.tools_called == []

    turn1_final = await handler.handle(
        turn1_query,
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
        confirmed_entities=[
            ConfirmedEntityRef(type="project", id=VILLA_48_ID, name="Villa Maintenance No. 48"),
        ],
    )
    assert not turn1_final.awaiting_clarification
    assert turn1_final.tools_called == ["get_project_expense_summary"]
    assert executor.expense_project_ids == [VILLA_48_ID]
    assert (turn1_final.visualization or {}).get("visual_type") == "PROJECT_EXPENSE_SUMMARY"

    turn2 = await handler.handle(
        "General maintenance work need expense report",
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
    )
    assert turn2.awaiting_clarification
    assert "get_project_expense_summary" not in turn2.tools_called
    assert VILLA_48_ID not in executor.expense_project_ids[1:]
    question = (turn2.clarification or {}).get("question") or turn2.text
    assert "pdf" not in question.lower()
    assert "excel" not in question.lower()

    turn3 = await handler.handle(
        "now General maintenance work",
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
    )
    assert VILLA_48_ID not in executor.expense_project_ids[1:]
    assert turn3.tools_called != ["get_project_expense_summary"]
    if turn3.tools_called:
        assert turn3.tools_called == ["search_entities"]
    else:
        assert turn3.awaiting_clarification
    scope = SessionScopeStore.get(session_id)
    assert scope.get("project_id") != VILLA_48_ID

    turn4 = await handler.handle(
        "give General maintenance work need expense report",
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
    )
    assert VILLA_48_ID not in executor.expense_project_ids[1:]
    assert not (
        turn4.tools_called == ["get_project_expense_summary"]
        and executor.expense_project_ids
        and executor.expense_project_ids[-1] == VILLA_48_ID
    )

    turn5_query = "General maintenance work - Al Mushrif need expense report"
    turn5_first = await handler.handle(
        turn5_query,
        user,
        adapter=object(),
        executor=executor,
        session_id=session_id,
    )

    if turn5_first.awaiting_clarification:
        turn5_final = await handler.handle(
            turn5_query,
            user,
            adapter=object(),
            executor=executor,
            session_id=session_id,
            confirmed_entities=[
                ConfirmedEntityRef(
                    type="project",
                    id=AL_MUSHRIF_ID,
                    name="General Maintenance Work - Al Mushrif",
                ),
            ],
        )
    else:
        turn5_final = turn5_first

    assert not turn5_final.awaiting_clarification
    assert "get_project_expense_summary" in turn5_final.tools_called
    assert executor.expense_project_ids[-1] == AL_MUSHRIF_ID
    assert executor.expense_project_ids[-1] != VILLA_48_ID


@pytest.mark.asyncio
async def test_incident_zero_data_gets_honest_message_not_on_track() -> None:
    """F4 guard: zero W.O + zero spend must not present as on-track success."""
    from gateway.core.quality_gate import QualityGate, QualityResponse, RetryHandler
    from gateway.core.quality_pipeline import QualityResponseReviser

    gate = QualityGate(retry_handler=RetryHandler(reviser=QualityResponseReviser()))
    response = QualityResponse(
        text="Villa Maintenance No. 48: total spend AED 0 of W.O AED 0. Status: on track.",
        visualization={
            "visual_type": "PROJECT_EXPENSE_SUMMARY",
            "project_name": "Villa Maintenance No. 48",
            "kpis": {
                "wo_amount": {"value": 0},
                "total_expenses": {"value": 0},
                "spend_pct": {"value": 0, "trend": {"context": "On track"}},
            },
        },
        suggestions=["Show breakdown"],
        tool_results=[{"wo_amount": 0, "total_expenses": 0, "_source": "project_expense_summary"}],
    )
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="Villa Maintenance No. 48 expense for this year",
    )

    final, review, _retries = await gate.ensure_quality(
        response,
        intent,
        _stack_for_user(_super_admin()),
    )

    assert "no expense data recorded" in final.text.lower()
    assert "on track" not in final.text.lower()
    not_all_zero = next(check for check in review.checks if check.name == "not_all_zero")
    assert not_all_zero.passed is True
