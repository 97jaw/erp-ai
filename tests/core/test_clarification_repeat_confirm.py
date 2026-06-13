"""Entity clarification repeat-query handling."""

from gateway.intelligent_handler import IntelligentQueryHandler


def test_queries_equivalent_when_user_adds_month_year() -> None:
    assert IntelligentQueryHandler._queries_equivalent_for_clarification(
        "jawad ur rehman",
        "jawad ur rehman, may 2026",
    )


def test_queries_equivalent_for_exact_repeat() -> None:
    assert IntelligentQueryHandler._queries_equivalent_for_clarification(
        "Villa Maintenance No. 34",
        "villa maintenance no. 34",
    )
