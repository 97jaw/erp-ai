"""Phase F1 — tool cache key must include user + entity identity."""

from __future__ import annotations

from gateway.tool_cache import ToolResultCache, build_tool_cache_key


def setup_function() -> None:
    ToolResultCache.clear()


def test_cache_key_includes_entity() -> None:
    key_a = build_tool_cache_key(
        1,
        "get_project_expense_summary",
        {"project_id": 3288, "project_name": "Villa 48"},
    )
    key_b = build_tool_cache_key(
        1,
        "get_project_expense_summary",
        {"project_id": 7711, "project_name": "Al Mushrif"},
    )
    assert key_a != key_b


def test_no_entity_in_input_uses_safe_key() -> None:
    key = build_tool_cache_key(1, "some_tool", {})
    assert "noid" in key
    assert "noent" in key


def test_different_projects_dont_share_cache() -> None:
    """Different entities must not share cache entries."""
    ToolResultCache.set(
        "get_project_expense_summary",
        {"project_id": 3288, "project_name": "Villa 48"},
        {"project_id": 3288, "project_name": "Villa 48", "total_expenses": 100},
        user_id=1,
    )
    ToolResultCache.set(
        "get_project_expense_summary",
        {"project_id": 7711, "project_name": "Al Mushrif"},
        {"project_id": 7711, "project_name": "Al Mushrif", "total_expenses": 200},
        user_id=1,
    )

    villa = ToolResultCache.get(
        "get_project_expense_summary",
        {"project_id": 3288, "project_name": "Villa 48"},
        user_id=1,
    )
    mushrif = ToolResultCache.get(
        "get_project_expense_summary",
        {"project_id": 7711, "project_name": "Al Mushrif"},
        user_id=1,
    )

    assert villa is not None
    assert mushrif is not None
    assert villa["project_id"] == 3288
    assert mushrif["project_id"] == 7711
    assert villa["total_expenses"] != mushrif["total_expenses"]


def test_different_users_dont_share_cache() -> None:
    ToolResultCache.set(
        "get_project_expense_summary",
        {"project_id": 3288, "project_name": "Villa 48"},
        {"project_id": 3288, "total_expenses": 100},
        user_id=1,
    )
    assert ToolResultCache.get(
        "get_project_expense_summary",
        {"project_id": 3288, "project_name": "Villa 48"},
        user_id=2,
    ) is None
