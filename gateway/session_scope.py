from __future__ import annotations

import json
from typing import Any


def _dedupe_list(items: list[Any]) -> list[Any]:
    """Merge list values without requiring hashable elements (e.g. dict rows)."""
    seen: set[str] = set()
    merged: list[Any] = []
    for item in items:
        if isinstance(item, (dict, list)):
            key = json.dumps(item, sort_keys=True, default=str)
        else:
            key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


HR_SESSION_KEYS = (
    "pending_hr_context",
    "last_payslip_scope",
)


class SessionScopeStore:
    """Lightweight structured memory for follow-up ERP queries."""

    _memory: dict[str, dict[str, Any]] = {}

    @classmethod
    def get(cls, session_id: str) -> dict[str, Any]:
        return dict(cls._memory.get(session_id) or {})

    @classmethod
    def clear(cls, session_id: str) -> None:
        """Remove all in-memory scope for a session thread."""
        cls._memory.pop(session_id, None)

    @classmethod
    def clear_entity_scope(cls, session_id: str) -> dict[str, Any]:
        """Remove project/partner entity bindings while keeping last_turn and other facts."""
        from gateway.core.topic_shift import ENTITY_SCOPE_KEYS

        current = dict(cls._memory.get(session_id) or {})
        for key in ENTITY_SCOPE_KEYS:
            current.pop(key, None)
        cls._memory[session_id] = current
        return dict(current)

    @classmethod
    def persist_hr_session(cls, session_id: str | None, working_memory: Any) -> None:
        """Persist HR/payroll follow-up slots so the next HTTP turn can inherit them."""
        if not session_id or working_memory is None:
            return
        facts = getattr(working_memory, "session_facts", None) or {}
        updates: dict[str, Any] = {}
        pending = facts.get("pending_hr_context")
        if isinstance(pending, dict) and pending:
            updates["pending_hr_context"] = dict(pending)
        last_scope = facts.get("last_payslip_scope")
        if isinstance(last_scope, dict) and last_scope:
            updates["last_payslip_scope"] = dict(last_scope)
        if updates:
            cls.update(session_id, **updates)

    @classmethod
    def update(cls, session_id: str, **values: Any) -> dict[str, Any]:
        current = cls.get(session_id)
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, list):
                current[key] = _dedupe_list([*current.get(key, []), *value])
            elif isinstance(value, dict):
                current[key] = {**current.get(key, {}), **value}
            else:
                current[key] = value
        cls._memory[session_id] = current
        return dict(current)
