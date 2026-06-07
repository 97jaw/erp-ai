"""Tests for gateway.core.user_context.UserContext."""

from datetime import datetime, timezone

import pytest

from gateway.core.user_context import UserContext


def _make_user(
    *,
    primary_role: str = "regular_user",
    level: int = 30,
    permissions: set[str] | None = None,
    name: str = "Test User",
) -> UserContext:
    return UserContext(
        user_id=4291,
        name=name,
        file_id="ELR-001",
        primary_role=primary_role,
        level=level,
        permissions=permissions or set(),
        primary_department="Finance",
        departments=["Finance"],
        preferred_language="en",
        preferred_currency="AED",
        default_date_range="last_3_months",
        response_style="brief",
        last_login=datetime(2026, 6, 6, 9, 0, tzinfo=timezone.utc),
        typical_queries=["Show P&L for last quarter"],
    )


def test_super_admin_gets_aggressive_assumption_level():
    user = _make_user(primary_role="super_admin", level=100)
    assert user.assumption_level() == "aggressive"


def test_top_management_gets_aggressive_assumption_level():
    user = _make_user(primary_role="top_management", level=70)
    assert user.assumption_level() == "aggressive"


def test_manager_gets_moderate_assumption_level():
    user = _make_user(primary_role="manager", level=50)
    assert user.assumption_level() == "moderate"


def test_regular_user_gets_conservative_assumption_level():
    user = _make_user(primary_role="regular_user", level=30)
    assert user.assumption_level() == "conservative"


def test_super_admin_has_access_breadth_all():
    user = _make_user(
        primary_role="super_admin",
        level=100,
        permissions={"data.all_projects"},
    )
    assert user.access_breadth() == "all"


def test_user_with_all_projects_permission_has_access_breadth_all():
    user = _make_user(
        primary_role="analyst",
        level=40,
        permissions={"data.all_projects"},
    )
    assert user.access_breadth() == "all"


def test_user_with_own_department_only_has_access_breadth_department():
    user = _make_user(
        primary_role="manager",
        level=50,
        permissions={"data.own_department_only"},
    )
    assert user.access_breadth() == "department"


def test_super_admin_behavior_rules_contain_searching_not_asking():
    user = _make_user(primary_role="super_admin", level=100)
    rules = user.behavior_rules()
    assert "SEARCHING, not asking" in rules


def test_summary_contains_user_role_and_name():
    user = _make_user(
        primary_role="super_admin",
        level=100,
        name="M Jawad",
        permissions={"data.all_projects"},
    )
    summary = user.summary()
    assert "M Jawad" in summary
    assert "super_admin" in summary


def test_summary_is_non_empty_usable_prompt_string():
    user = _make_user(primary_role="manager", level=50)
    summary = user.summary()
    assert isinstance(summary, str)
    assert summary.strip()
    assert "User:" in summary
    assert "CRITICAL:" in summary
    assert user.assumption_level() in summary
