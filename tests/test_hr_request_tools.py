"""Tests for HR request detail tools."""

from gateway.core.hr_payroll_composer import extract_request_reference
from gateway.hr_request_tools import _present_request, _present_validation


def test_extract_request_reference_numeric() -> None:
    assert extract_request_reference("validation status request id 8834") == (8834, None)
    assert extract_request_reference("45231") == (45231, None)


def test_extract_request_reference_code() -> None:
    assert extract_request_reference("show ER-2026/0042 validation") == (None, "ER-2026/0042")


def test_present_request_includes_leave_period() -> None:
    row = {
        "id": 10,
        "name": "Leave May",
        "employee_id": [1, "Jawad"],
        "request_type_id": [2, "Leave"],
        "status": "approve",
        "is_approve": True,
        "create_date": "2026-05-01",
        "date_from": "2026-05-10",
        "date_to": "2026-05-12",
        "number_of_days": 3,
    }
    presented = _present_request(row)
    assert presented["leave_period"] == "2026-05-10 to 2026-05-12"
    assert presented["number_of_days"] == 3


def test_present_validation_row() -> None:
    row = {
        "id": 1,
        "name": "Manager approval",
        "status": "approved",
        "user_id": [5, "HR Manager"],
        "date": "2026-05-02",
        "sequence": 1,
    }
    presented = _present_validation(row)
    assert presented["approver"] == "HR Manager"
    assert presented["status"] == "approved"
