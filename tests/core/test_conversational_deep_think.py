"""Tests for conversational routing and Deep Think mode separation."""

from __future__ import annotations

from typing import Any

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.conversational_responder import (
    ConversationalResponder,
    NormalModeResponder,
    conversational_suggestions,
    is_conversational_intent,
    is_conversational_message,
    normal_mode_suggestions,
)
from gateway.core.deep_think import is_deep_think_eligible
from gateway.core.intent_analyzer import Intent
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_execution_orchestrator import MockToolExecutor


class FakeTextClient:
    """Records calls and returns a fixed reply without hitting Claude."""

    def __init__(self, reply: str = "Hello! How can I help with your ERP data?") -> None:
        self.reply = reply
        self.calls: list[dict[str, str]] = []

    async def complete_text(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        max_tokens: int = 600,
    ) -> str:
        self.calls.append({"system": system, "prompt": prompt})
        return self.reply


class ExplodingIntentAnalyzer:
    """Fails the test if intent analysis (a Claude call) is ever attempted."""

    async def analyze(self, query: str, context: Any) -> Intent:
        raise AssertionError(f"Intent analysis must not run for {query!r}")


class FixedIntentAnalyzer:
    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    async def analyze(self, query: str, context: Any) -> Intent:
        return self.intent


def _user() -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="2721",
        name="M Jawad",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )


# ---------------------------------------------------------------------------
# Conversational detection
# ---------------------------------------------------------------------------


def test_is_conversational_message_greetings() -> None:
    assert is_conversational_message("Hi")
    assert is_conversational_message("hello!")
    assert is_conversational_message("Hey")
    assert is_conversational_message("thanks")
    assert is_conversational_message("Thank you!")
    assert is_conversational_message("مرحبا")
    assert is_conversational_message("شكرا")


def test_is_conversational_message_capability_questions() -> None:
    assert is_conversational_message("what can you do?")
    assert is_conversational_message("How can you help me?")
    assert is_conversational_message("who are you")


def test_is_conversational_message_rejects_business_queries() -> None:
    assert not is_conversational_message("show me the P&L")
    assert not is_conversational_message("villa 34 expenses")
    assert not is_conversational_message("hi, show me project expenses")
    assert not is_conversational_message("trial balance for last quarter")
    assert not is_conversational_message("")


def test_is_conversational_intent_general_chat() -> None:
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="greeting",
    )
    assert is_conversational_intent(intent, "good morning team")


def test_is_conversational_intent_rejects_business_signal() -> None:
    intent = Intent(
        primary_action="ask_question",
        subject_area="general",
        specific_intent="misc",
    )
    assert not is_conversational_intent(intent, "what is our revenue")


# ---------------------------------------------------------------------------
# Deep Think eligibility
# ---------------------------------------------------------------------------


def test_deep_think_eligible_financial_queries() -> None:
    assert is_deep_think_eligible("show me the P&L")
    assert is_deep_think_eligible("trial balance for Q1")
    assert is_deep_think_eligible("Villa Maintenance No. 34 expenses")
    assert is_deep_think_eligible("compare project expenses for Zayidia schools")
    assert is_deep_think_eligible("receivables ageing summary")


def test_deep_think_not_eligible_conversational() -> None:
    assert not is_deep_think_eligible("Hi")
    assert not is_deep_think_eligible("thanks!")
    assert not is_deep_think_eligible("ok")
    assert not is_deep_think_eligible("")


# ---------------------------------------------------------------------------
# Handler routing: greetings never touch tools or Odoo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hi_returns_conversational_reply_without_intent_or_tools() -> None:
    fake = FakeTextClient(reply="Hello M Jawad! How can I help with Elrace data today?")
    handler = IntelligentQueryHandler(
        intent_analyzer=ExplodingIntentAnalyzer(),
        conversational_responder=ConversationalResponder(client=fake),
    )
    response = await handler.handle("Hi", _user(), adapter=object())

    assert response.failure_mode is None
    assert response.tools_called == []
    assert response.strategy_step_count == 0
    assert "hello" in response.text.lower()
    assert len(fake.calls) == 1
    assert response.suggestions == conversational_suggestions("en")


@pytest.mark.asyncio
async def test_capability_question_routes_conversationally() -> None:
    fake = FakeTextClient(reply="I can pull P&L, project expenses, and partner ledgers.")
    handler = IntelligentQueryHandler(
        intent_analyzer=ExplodingIntentAnalyzer(),
        conversational_responder=ConversationalResponder(client=fake),
    )
    response = await handler.handle("what can you do?", _user(), adapter=object())

    assert response.failure_mode is None
    assert response.tools_called == []
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_off_topic_general_intent_routes_conversationally() -> None:
    fake = FakeTextClient(reply="I focus on Elrace ERP data — happy to help with reports.")
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="off-topic weather question",
    )
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(intent),
        conversational_responder=ConversationalResponder(client=fake),
    )
    response = await handler.handle(
        "what's the weather in Dubai today?",
        _user(),
        adapter=object(),
    )

    assert response.failure_mode is None
    assert response.tools_called == []
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_conversational_fallback_when_claude_fails() -> None:
    class FailingClient:
        async def complete_text(self, **kwargs: Any) -> str:
            raise RuntimeError("api down")

    handler = IntelligentQueryHandler(
        intent_analyzer=ExplodingIntentAnalyzer(),
        conversational_responder=ConversationalResponder(client=FailingClient()),
    )
    response = await handler.handle("Hi", _user(), adapter=object())

    assert response.failure_mode is None
    assert "elrace" in response.text.lower()


# ---------------------------------------------------------------------------
# Mode separation: normal mode vs Deep Think
# ---------------------------------------------------------------------------


def _financial_intent() -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="show trial balance",
        estimated_complexity="simple",
        expected_output="table",
    )


@pytest.mark.asyncio
async def test_financial_query_without_deep_think_gets_ai_prepared_answer() -> None:
    fake = FakeTextClient(
        reply="You want the trial balance. Activate Deep Think to pull the figures.",
    )
    executor = MockToolExecutor()
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_financial_intent()),
        normal_mode_responder=NormalModeResponder(client=fake),
    )
    response = await handler.handle(
        "show me the trial balance",
        _user(),
        adapter=object(),
        skip_clarification=True,
        executor=executor,
    )

    assert response.deep_think_available is True
    assert response.tools_called == []
    assert executor.calls == []
    assert "deep think" in response.text.lower()
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_financial_query_with_deep_think_runs_odoo_tools() -> None:
    fake = FakeTextClient()
    executor = MockToolExecutor(
        responses={
            ("get_trial_balance", 1): {
                "rows": [{"account": "4000", "debit": 0, "credit": 1000}],
            },
        },
    )
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_financial_intent()),
        normal_mode_responder=NormalModeResponder(client=fake),
    )
    response = await handler.handle(
        "show me the trial balance",
        _user(),
        adapter=object(),
        skip_clarification=True,
        executor=executor,
        deep_think=True,
    )

    assert response.deep_think_available is False
    assert len(executor.calls) >= 1
    assert executor.calls[0][0] == "get_trial_balance"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_normal_mode_never_fabricates_via_responder_prompt() -> None:
    fake = FakeTextClient(reply="Understood — Deep Think will pull the data.")
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_financial_intent()),
        normal_mode_responder=NormalModeResponder(client=fake),
    )
    await handler.handle(
        "show me the trial balance",
        _user(),
        adapter=object(),
        skip_clarification=True,
    )

    system_prompt = fake.calls[0]["system"]
    assert "NEVER output any financial figures" in system_prompt
    assert "Deep Think" in system_prompt


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def test_conversational_suggestions_are_capability_chips() -> None:
    chips = conversational_suggestions("en")
    assert len(chips) == 3
    assert any("P&L" in chip for chip in chips)
    chips_ar = conversational_suggestions("ar")
    assert len(chips_ar) == 3


def test_normal_mode_suggestions_interpolate_query_and_project() -> None:
    context = _make_context_stack()
    context.working_memory.set_active_project(15157, "Villa Maintenance No. 34")
    chips = normal_mode_suggestions("show me the expenses", context, "en")
    assert any("last 3 months" in chip for chip in chips)
    assert any("Villa Maintenance No. 34" in chip for chip in chips)


def test_normal_mode_suggestions_skip_period_when_present() -> None:
    context = _make_context_stack()
    chips = normal_mode_suggestions("P&L for last month", context, "en")
    assert all("P&L for last month for the last 3 months" != chip for chip in chips)


def test_smart_suggestions_interpolate_date_range_and_project() -> None:
    from gateway.core.smart_suggestions import SmartSuggestionsGenerator

    context = _make_context_stack()
    context.working_memory.set_active_project(15157, "Villa Maintenance No. 34")
    tool_results = [
        {
            "date_from": "2026-03-01",
            "date_to": "2026-06-01",
            "rows": [],
        },
    ]
    suggestions = SmartSuggestionsGenerator._context_interpolated_suggestions(
        context,
        tool_results,
    )
    texts = [item.text for item in suggestions]
    assert any("Villa Maintenance No. 34" in text for text in texts)
    assert any("2026-03-01" in text and "2026-06-01" in text for text in texts)


def test_executed_date_range_reads_used_context() -> None:
    from gateway.core.smart_suggestions import _executed_date_range

    results = [{"used_context": {"date_from": "2026-01-01", "date_to": "2026-03-31"}}]
    assert _executed_date_range(results) == ("2026-01-01", "2026-03-31")
    assert _executed_date_range([]) == (None, None)
    assert _executed_date_range([{"rows": []}]) == (None, None)
