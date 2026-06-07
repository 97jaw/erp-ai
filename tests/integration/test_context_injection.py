"""Integration tests for context stack injection into the intelligence pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from admin.auth.principal import CurrentUser
from admin.rbac.context import set_request_user
from gateway.core.context_stack import ContextStack
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.intent_analyzer import Intent
from gateway.intelligent_handler import IntelligentQueryHandler


@dataclass
class SimpleChatRequest:
    message: str
    session_id: str | None = None


def _make_super_admin() -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin User",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
        department_codes=("Finance",),
    )


def _make_regular_user() -> CurrentUser:
    return CurrentUser(
        id=5001,
        file_id="USR-5001",
        name="Regular User",
        language="en",
        is_super_admin=False,
        is_active=True,
        roles=("user",),
        permissions=frozenset(),
        department_ids=(2,),
        department_codes=("Operations",),
    )


class _OutOfScopeAnalyzer:
    async def analyze(self, query: str, context: ContextStack) -> Intent:
        del context
        return Intent(
            primary_action="fetch_data",
            subject_area="financial",
            specific_intent=query,
            out_of_scope=True,
            out_of_scope_reason="Test out of scope",
        )


@pytest.mark.asyncio
async def test_chat_endpoint_builds_context_stack_for_each_request() -> None:
    from gateway import main

    build_mock = AsyncMock(wraps=ContextStackBuilder().build)
    main._intelligent_query_handler = IntelligentQueryHandler(
        intent_analyzer=_OutOfScopeAnalyzer(),
    )

    set_request_user(_make_super_admin())
    try:
        with patch.object(ContextStackBuilder, "build", build_mock):
            with patch.object(main, "get_adapter", return_value=MagicMock()):
                with patch.object(main, "ConversationStore") as store:
                    store.append = AsyncMock(return_value=[])
                    store.get = AsyncMock(return_value=[{}, {}])
                    store.conversation_id_for_session.return_value = "conv-1"
                    await main._run_intelligent_chat(
                        "Show P&L",
                        "session-ctx-1",
                        _make_super_admin(),
                    )
    finally:
        main._intelligent_query_handler = None
        set_request_user(None)

    build_mock.assert_called_once()
    args, _kwargs = build_mock.call_args
    assert isinstance(args[0], CurrentUser)
    assert args[1].message == "Show P&L"
    assert args[1].session_id == "session-ctx-1"


async def _build_prompt_for_user(user: CurrentUser, message: str) -> str:
    from gateway import main

    with patch(
        "gateway.hr_payroll_tools.build_hr_identity_prompt",
        new=AsyncMock(return_value=""),
    ):
        with patch(
            "gateway.core.intelligence_preflight.build_intelligence_preflight_section",
            new=AsyncMock(return_value=""),
        ):
            return await main._build_agent_system_prompt(
                "Friday, 06 June 2026",
                user_message=message,
                adapter=MagicMock(),
                session_id=None,
                user=user,
            )


@pytest.mark.asyncio
async def test_claude_system_prompt_contains_user_context_section() -> None:
    prompt = await _build_prompt_for_user(_make_super_admin(), "Show trial balance")
    assert "=== USER CONTEXT ===" in prompt


@pytest.mark.asyncio
async def test_claude_system_prompt_contains_user_role() -> None:
    prompt = await _build_prompt_for_user(_make_super_admin(), "Show trial balance")
    assert "super_admin" in prompt


@pytest.mark.asyncio
async def test_claude_system_prompt_contains_cannot_do_capability_list() -> None:
    prompt = await _build_prompt_for_user(_make_regular_user(), "Show my payslip")
    assert "CANNOT DO" in prompt
    assert "hr.payslips" in prompt


@pytest.mark.asyncio
async def test_super_admin_gets_aggressive_behavior_instruction_in_prompt() -> None:
    prompt = await _build_prompt_for_user(_make_super_admin(), "Show all projects")
    assert "Assumption Level: aggressive" in prompt


@pytest.mark.asyncio
async def test_regular_user_gets_conservative_instruction_in_prompt() -> None:
    prompt = await _build_prompt_for_user(_make_regular_user(), "Show my expenses")
    assert "Assumption Level: conservative" in prompt


@pytest.mark.asyncio
async def test_context_building_does_not_exceed_500ms() -> None:
    builder = ContextStackBuilder()
    request = SimpleChatRequest(message="Show P&L", session_id="session-perf")

    started = time.perf_counter()
    stack = await builder.build(_make_super_admin(), request)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert isinstance(stack, ContextStack)
    assert elapsed_ms < 500
