"""Paginated table data for progressive disclosure (Phase 4)."""
from __future__ import annotations

import time
import uuid
from typing import Any

DEFAULT_PAGE_SIZE = 20
CACHE_TTL_SECONDS = 3600


class QueryPageStore:
    """In-process cache of tabular query results keyed by query_id."""

    _entries: dict[str, tuple[float, dict[str, Any]]] = {}

    @classmethod
    def _purge_expired(cls) -> None:
        now = time.monotonic()
        expired = [key for key, (expires_at, _) in cls._entries.items() if now >= expires_at]
        for key in expired:
            cls._entries.pop(key, None)

    @classmethod
    def register(
        cls,
        *,
        headers: list[Any],
        rows: list[Any],
        label: str = "",
        visual_type: str = "DATA_TABLE",
        meta: dict[str, Any] | None = None,
    ) -> str:
        cls._purge_expired()
        query_id = uuid.uuid4().hex
        cls._entries[query_id] = (
            time.monotonic() + CACHE_TTL_SECONDS,
            {
                "headers": headers,
                "rows": rows,
                "label": label,
                "visual_type": visual_type,
                "meta": meta or {},
            },
        )
        return query_id

    @classmethod
    def get(cls, query_id: str) -> dict[str, Any] | None:
        cls._purge_expired()
        entry = cls._entries.get(query_id)
        if not entry:
            return None
        expires_at, payload = entry
        if time.monotonic() >= expires_at:
            cls._entries.pop(query_id, None)
            return None
        return payload

    @classmethod
    def get_page(
        cls,
        query_id: str,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> dict[str, Any]:
        payload = cls.get(query_id)
        if not payload:
            raise KeyError(query_id)

        headers = list(payload.get("headers") or [])
        rows = [list(row) if isinstance(row, (list, tuple)) else row for row in payload.get("rows") or []]
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or DEFAULT_PAGE_SIZE), 100))

        if sort_by and headers:
            try:
                column_index = headers.index(sort_by)
            except ValueError:
                column_index = 0

            def sort_key(row: Any) -> tuple[int, Any]:
                if not isinstance(row, (list, tuple)) or column_index >= len(row):
                    return (1, "")
                value = row[column_index]
                try:
                    return (0, float(value))
                except (TypeError, ValueError):
                    return (0, str(value).lower())

            rows = sorted(rows, key=sort_key, reverse=sort_dir.lower() != "asc")

        total = len(rows)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        page_rows = rows[offset: offset + page_size]

        return {
            "query_id": query_id,
            "label": payload.get("label") or "",
            "visual_type": payload.get("visual_type") or "DATA_TABLE",
            "headers": headers,
            "rows": page_rows,
            "meta": payload.get("meta") or {},
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            },
        }
