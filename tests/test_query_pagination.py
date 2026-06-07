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
