from __future__ import annotations

import pytest

from gateway.query_pagination import QueryPageStore


def test_query_page_store_returns_slices() -> None:
    query_id = QueryPageStore.register(
        headers=["Account", "Balance"],
        rows=[[f"Row {index}", float(index)] for index in range(45)],
        label="Accounts",
    )
    page_1 = QueryPageStore.get_page(query_id, page=1, page_size=20)
    assert len(page_1["rows"]) == 20
    assert page_1["pagination"]["total_records"] == 45
    assert page_1["pagination"]["has_next"] is True

    page_2 = QueryPageStore.get_page(query_id, page=2, page_size=20)
    assert len(page_2["rows"]) == 20
    assert page_2["pagination"]["has_prev"] is True


def test_query_page_store_missing_id() -> None:
    with pytest.raises(KeyError):
        QueryPageStore.get_page("missing-id", page=1)


def test_query_page_store_get_full_returns_all_rows() -> None:
    query_id = QueryPageStore.register(
        headers=["Account", "Balance"],
        rows=[[f"Row {index}", float(index)] for index in range(200)],
        label="Accounts",
    )
    page = QueryPageStore.get_page(query_id, page=1, page_size=100)
    assert len(page["rows"]) == 100
    assert page["pagination"]["total_records"] == 200

    full = QueryPageStore.get_full(query_id)
    assert len(full["rows"]) == 200
    assert full["total_records"] == 200
    assert full["headers"] == ["Account", "Balance"]
