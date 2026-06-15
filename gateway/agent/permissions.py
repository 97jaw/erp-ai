"""Role-based tool access for the unified agent."""

from __future__ import annotations

from typing import Any

SUPER_ADMIN_ONLY_TOOLS = frozenset(
    {
        "get_partner_ledger",
    }
)


def user_role_label(user: Any | None) -> str:
    """Human-readable role for system prompt."""
    if user is None:
        return "anonymous"
    if getattr(user, "is_super_admin", False):
        return "super_admin"
    roles = getattr(user, "roles", ()) or ()
    if roles:
        return str(roles[0])
    return "standard_user"


def user_level(user: Any | None) -> int:
    """Numeric level for permission checks (100 = super admin)."""
    if user is None:
        return 70
    if getattr(user, "is_super_admin", False):
        return 100
    return 70


def filter_tools_for_user(tools: list[dict[str, Any]], user: Any | None) -> list[dict[str, Any]]:
    """Remove tools the user cannot access."""
    if user_level(user) >= 100:
        return tools
    return [tool for tool in tools if tool.get("name") not in SUPER_ADMIN_ONLY_TOOLS]
