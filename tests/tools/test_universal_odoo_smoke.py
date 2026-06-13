"""M0 smoke tests for universal Odoo tools (mocked adapter)."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.tools.universal_odoo import (
    build_universal_context,
    execute_aggregate_odoo,
    execute_query_odoo,
)


class MockAdapter:
    def __init__(self) -> None:
        self.safe_search_read_calls: list[tuple[Any, ...]] = []
        self.read_group_calls: list[tuple[Any, ...]] = []
        self.search_count_calls: list[tuple[Any, ...]] = []

    def search_count(self, model: str, domain: list[Any]) -> int:
        self.search_count_calls.append((model, domain))
        return 12

    def safe_search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        del offset, order
        self.safe_search_read_calls.append((model, domain, fields, limit))
        if model == "hr.employee":
            return [
                {"id": i, "name": f"Employee {i}", "department_id": [1, "Ops"]}
                for i in range(1, 6)
            ]
        return []

    def read_group(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        groupby: list[str],
        limit: int = 80,
        offset: int = 0,
        order: str | None = None,
        lazy: bool = True,
    ) -> list[dict[str, Any]]:
        del domain, offset, order, lazy
        self.read_group_calls.append((model, fields, groupby, limit))
        return [
            {"department_id": (1, "Operations"), "department_id_count": 12, "__domain": []},
            {"department_id": (2, "Finance"), "department_id_count": 5, "__domain": []},
        ]


@pytest.mark.asyncio
async def test_query_odoo_hr_employee_returns_five() -> None:
    adapter = MockAdapter()
    ctx = build_universal_context()
    result = await execute_query_odoo(
        adapter,
        {
            "model": "hr.employee",
            "domain": [["active", "=", True]],
            "fields": ["name", "department_id"],
            "limit": 5,
        },
        ctx,
    )
    assert result["status"] == "success"
    assert result["record_count"] == 5
    assert len(result["records"]) == 5


@pytest.mark.asyncio
async def test_aggregate_odoo_employees_per_department() -> None:
    adapter = MockAdapter()
    ctx = build_universal_context()
    result = await execute_aggregate_odoo(
        adapter,
        {
            "model": "hr.employee",
            "domain": [["active", "=", True]],
            "group_by": ["department_id"],
            "aggregates": ["id:count"],
        },
        ctx,
    )
    assert result["status"] == "success"
    assert result["group_count"] == 2
    assert adapter.read_group_calls


@pytest.mark.asyncio
async def test_aggregate_odoo_total_count_without_group_by() -> None:
    adapter = MockAdapter()
    ctx = build_universal_context()
    result = await execute_aggregate_odoo(
        adapter,
        {
            "model": "employee.requests",
            "domain": [["request_type_id.name", "ilike", "termination"]],
            "group_by": [],
            "aggregates": ["id:count"],
        },
        ctx,
    )
    assert result["status"] == "success"
    assert result["groups"] == [{"__count": 12}]
    assert adapter.search_count_calls
    assert adapter.read_group_calls == []


@pytest.mark.asyncio
async def test_query_odoo_res_users_blocked() -> None:
    adapter = MockAdapter()
    ctx = build_universal_context()
    result = await execute_query_odoo(
        adapter,
        {"model": "res.users", "fields": ["name", "login"], "limit": 5},
        ctx,
    )
    assert result["status"] == "error"
    assert result["error_code"] == "model_forbidden"
    assert adapter.safe_search_read_calls == []
