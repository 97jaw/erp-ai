from unittest.mock import MagicMock

from admin.auth.principal import CurrentUser
from gateway.query_limits import (
    apply_query_limits_to_tool_input,
    default_limit_for_user,
    execute_search_odoo,
    max_limit_for_user,
)


def _super_admin() -> CurrentUser:
    return CurrentUser(
        id=1,
        file_id="2721",
        name="Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
    )


def test_super_admin_default_limit_is_high():
    user = _super_admin()
    assert default_limit_for_user(user) >= 500
    assert max_limit_for_user(user) >= 500


def test_apply_query_limits_sets_default_when_missing():
    user = _super_admin()
    scoped = apply_query_limits_to_tool_input(
        "search_odoo",
        {"model": "project.project", "fields": ["name"]},
        user,
    )
    assert scoped["limit"] >= 500
    assert scoped.get("_limit_meta", {}).get("limit_defaulted") is True


def test_execute_search_odoo_includes_meta():
    adapter = MagicMock()
    adapter.search_read.return_value = [{"id": 1, "name": "P1"}]
    adapter.search_count.return_value = 42

    user = _super_admin()
    result = execute_search_odoo(
        adapter,
        {
            "model": "project.project",
            "filters": [["active", "=", True]],
            "fields": ["name"],
            "limit": 100,
            "_limit_meta": {"limit_applied": 100},
        },
        user,
    )
    assert result["records"][0]["name"] == "P1"
    meta = result["_query_meta"]
    assert meta["total_matching"] == 42
    assert meta["truncated"] is True
    assert meta["returned_count"] == 1
