from __future__ import annotations

from datetime import date, datetime


def resolve_date_range(
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, str]:
    today = date.today()
    resolved_to = date_to or today.isoformat()
    if date_from:
        return date_from, resolved_to
    month_start = today.replace(day=1)
    return month_start.isoformat(), resolved_to


def resolve_as_of_date(as_of_date: str | None, date_to: str | None) -> str:
    return as_of_date or date_to or date.today().isoformat()
