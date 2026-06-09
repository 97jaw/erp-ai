"""Tests for session scope hydration in ContextStackBuilder."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from admin.auth.principal import CurrentUser
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.session_scope import SessionScopeStore


@dataclass
class _Request:
    message: str
    session_id: str | None


def _super_admin() -> CurrentUser:
    return CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )


@pytest.mark.asyncio
async def test_context_builder_hydrates_expense_scope() -> None:
    session_id = "scope-hydrate-test"
    SessionScopeStore.update(
        session_id,
        project_id=31034,
        project_name="Villa Maintenance No. 34",
        last_expense_summary_project_id=31034,
    )

    stack = await ContextStackBuilder().build(
        _super_admin(),
        _Request(message="show me cost break down as well", session_id=session_id),
    )

    facts = stack.working_memory.session_facts
    assert facts["resolved_project_id"] == 31034
    assert facts["last_expense_summary_project_id"] == 31034
    assert facts["project_name"] == "Villa Maintenance No. 34"
    assert facts["confirmed_entities"]["project"]["id"] == 31034
