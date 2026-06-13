"""Tests for HR clarification builders."""

from gateway.core.hr_clarification import build_employee_disambiguation_clarification


def test_employee_disambiguation_options_have_query_suffix() -> None:
    clarification = build_employee_disambiguation_clarification(
        query="need payslip for jawad may 2026",
        employees=[
            {"id": 1, "name": "Jawad Ahmad", "emp_id": "2591"},
            {"id": 2, "name": "Muhammad Jawad Ur Rehman", "emp_id": "2721"},
        ],
        subtype="payslip_header",
    )
    options = clarification.get("options") or []
    assert len(options) == 2
    assert options[0].get("query_suffix") == " file id 2591"
    assert options[1].get("query_suffix") == " file id 2721"
    assert options[0].get("action") == "confirm_hr_employee"
