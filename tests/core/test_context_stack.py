"""Tests for gateway.core.context_stack and ContextStackBuilder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.business_context import BusinessContext
from gateway.core.capability_manifest import CAPABILITY_MANIFEST
from gateway.core.context_stack import (
    ContextStack,
    ConversationContext,
    QualityTargets,
)
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.temporal_context import TemporalContext
from gateway.core.user_context import UserContext
from gateway.core.working_memory import WorkingMemory


@dataclass
class SimpleChatRequest:
    message: str
    session_id: str | None = None


def _make_user_context(*, primary_role: str = "regular_user", level: int = 30) -> UserContext:
    return UserContext(
        user_id=4291,
        name="M Jawad",
        file_id="ELR-001",
        primary_role=primary_role,
        level=level,
        permissions=set(),
        primary_department="Finance",
        departments=["Finance"],
        preferred_language="en",
        preferred_currency="AED",
        default_date_range="last_3_months",
        response_style="brief",
        last_login=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
        typical_queries=[],
    )


def _make_context_stack(*, primary_role: str = "regular_user", level: int = 30) -> ContextStack:
    return ContextStack(
        user=_make_user_context(primary_role=primary_role, level=level),
        conversation=ConversationContext(
            session_id="session-123",
            message="Show P&L for last quarter",
        ),
        capability_manifest=CAPABILITY_MANIFEST,
        working_memory=WorkingMemory(),
        business_context=BusinessContext(),
        temporal_context=TemporalContext.build(datetime(2026, 6, 6, tzinfo=timezone.utc)),
        quality_targets=QualityTargets(),
    )


def _make_current_user(
    *,
    name: str = "M Jawad",
    is_super_admin: bool = False,
    roles: tuple[str, ...] = ("user",),
    permissions: frozenset[str] = frozenset(),
) -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="ELR-001",
        name=name,
        language="en",
        is_super_admin=is_super_admin,
        is_active=True,
        roles=roles,
        permissions=permissions,
        department_ids=(1,),
        department_codes=("Finance",),
    )


def test_context_stack_can_be_instantiated_with_all_components():
    stack = _make_context_stack()
    assert isinstance(stack.user, UserContext)
    assert isinstance(stack.conversation, ConversationContext)
    assert stack.capability_manifest is CAPABILITY_MANIFEST
    assert isinstance(stack.working_memory, WorkingMemory)
    assert isinstance(stack.business_context, BusinessContext)
    assert isinstance(stack.temporal_context, TemporalContext)
    assert isinstance(stack.quality_targets, QualityTargets)


def test_to_prompt_section_returns_long_non_empty_string():
    prompt = _make_context_stack().to_prompt_section()
    assert isinstance(prompt, str)
    assert len(prompt.strip()) > 200


def test_to_prompt_section_contains_user_context_section():
    assert "=== USER CONTEXT ===" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_capabilities_section():
    assert "=== CAPABILITIES ===" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_working_memory_section():
    assert "=== WORKING MEMORY ===" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_temporal_context_section():
    assert "=== TEMPORAL CONTEXT ===" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_user_name():
    assert "M Jawad" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_role():
    assert "regular_user" in _make_context_stack().to_prompt_section()


def test_to_prompt_section_contains_last_3_months_default_reference():
    prompt = _make_context_stack().to_prompt_section()
    assert "last 3 months" in prompt.lower()


@pytest.mark.asyncio
async def test_context_stack_builder_build_returns_context_stack():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(),
        SimpleChatRequest(message="Show trial balance"),
    )
    assert isinstance(stack, ContextStack)


@pytest.mark.asyncio
async def test_context_stack_builder_build_works_for_super_admin():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(is_super_admin=True, roles=("super_admin",)),
        SimpleChatRequest(message="Show all projects"),
    )
    assert stack.user.primary_role == "super_admin"
    assert stack.user.level == 100


@pytest.mark.asyncio
async def test_context_stack_builder_build_works_for_regular_user():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(roles=("user",)),
        SimpleChatRequest(message="Show my department expenses"),
    )
    assert stack.user.primary_role == "user"
    assert stack.user.level == 30


@pytest.mark.asyncio
async def test_super_admin_context_has_aggressive_assumption_level_in_prompt():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(is_super_admin=True, roles=("super_admin",)),
        SimpleChatRequest(message="Show P&L"),
    )
    prompt = stack.to_prompt_section()
    assert "Assumption Level: aggressive" in prompt


@pytest.mark.asyncio
async def test_regular_user_context_has_conservative_assumption_level_in_prompt():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(roles=("user",)),
        SimpleChatRequest(message="Show P&L"),
    )
    prompt = stack.to_prompt_section()
    assert "Assumption Level: conservative" in prompt


@pytest.mark.asyncio
async def test_payslip_appears_in_can_do_section_of_capability_output():
    builder = ContextStackBuilder()
    stack = await builder.build(
        _make_current_user(),
        SimpleChatRequest(message="Show my payslip"),
    )
    prompt = stack.to_prompt_section()
    assert "WHAT YOU CAN DO" in prompt
    assert "hr.payslips" in prompt
