from unittest.mock import MagicMock

from admin.auth.principal import CurrentUser
from gateway.hr_identity import resolve_employee_by_file_id
from gateway.hr_payroll_tools import _and_domain, _filter_payslip_lines, _present_payslip
from gateway.core.hr_payroll_composer import payslip_period_domain_from_dates


def test_present_payslip_amount_prefers_net_wage():
    row = {
        "id": 1,
        "name": "Payslip Jan",
        "employee_id": [5, "Jane"],
        "net_wage": 15000.0,
        "gross_wage": 18000.0,
        "state": "done",
    }
    out = _present_payslip(row)
    assert out["amount"] == 15000.0
    assert out["employee_name"] == "Jane"


def test_resolve_employee_by_emp_id():
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "id": {},
        "name": {},
        "emp_id": {},
        "active": {},
    }
    adapter.search_read.return_value = [
        {"id": 9, "name": "Test User", "emp_id": "2721"},
    ]
    employee, strategy = resolve_employee_by_file_id(adapter, "2721")
    assert employee is not None
    assert employee["id"] == 9
    assert strategy == "emp_id"


def test_get_my_payslips_no_employee_note():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from gateway.hr_payroll_tools import get_my_payslips

    adapter = MagicMock()
    adapter._get_model_fields.side_effect = lambda model: (
        {"id": {}, "name": {}, "state": {}, "employee_id": {}, "net_wage": {}}
        if model == "hr.payslip"
        else {"id": {}, "name": {}, "emp_id": {}, "active": {}}
    )
    adapter.search_read.return_value = []
    user = CurrentUser(
        id=1,
        file_id="2721",
        name="Test",
        language="en",
        is_super_admin=True,
        is_active=True,
    )

    with patch(
        "gateway.hr_payroll_tools.resolve_odoo_user_id",
        new=AsyncMock(return_value=None),
    ), patch(
        "gateway.hr_payroll_tools.resolve_employee_by_file_id",
        return_value=(None, None),
    ), patch(
        "gateway.hr_payroll_tools.fetch_recent_payslips",
        return_value={"payslips": [], "count": 0},
    ):
        result = asyncio.run(get_my_payslips(adapter, user))
    assert result["count"] == 0
    assert "emp_id" in result.get("note", "").lower() or "payslip" in result.get("note", "").lower()


def test_fetch_recent_payslips_returns_rows():
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "id": {},
        "state": {},
        "employee_id": {},
        "net_wage": {},
        "date_to": {},
    }
    adapter.search_read.return_value = [
        {
            "id": 1,
            "name": "SLIP/001",
            "employee_id": [2, "Jane"],
            "state": "done",
            "net_wage": 100.0,
        },
    ]
    from gateway.hr_payroll_tools import fetch_recent_payslips

    out = fetch_recent_payslips(adapter, limit=5)
    assert out["count"] == 1
    assert out["payslips"][0]["employee_name"] == "Jane"


def test_filter_payslip_lines_overtime() -> None:
    lines = [
        {"name": "Normal Overtime", "code": "NOT", "amount": 100.0, "category_id": [1, "Allowance"]},
        {"name": "Basic Salary", "code": "BASIC", "amount": 1200.0, "category_id": [2, "Basic"]},
    ]
    filtered = _filter_payslip_lines(lines, "overtime")
    assert len(filtered) == 1
    assert filtered[0]["code"] == "NOT"


def test_and_domain_merges_employee_with_payslip_period() -> None:
    period = payslip_period_domain_from_dates("2026-05-01", "2026-05-31")
    domain = _and_domain([["employee_id", "=", 4255]], period)
    assert domain[0] == "&"
    assert domain[1] == ["employee_id", "=", 4255]
    assert "|" in domain
    assert ["name", "ilike", "May-2026"] in domain
