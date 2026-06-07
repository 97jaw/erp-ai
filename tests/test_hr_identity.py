from unittest.mock import MagicMock

from admin.auth.principal import CurrentUser
from gateway.hr_identity import (
    apply_personal_hr_scope,
    can_access_employee_file_id,
    can_query_other_employees,
    normalize_employee_file_id,
    resolve_employee_by_file_id,
)


def test_normalize_file_id_strips_spaces():
    assert normalize_employee_file_id(" 2721 ") == "2721"


def test_resolve_employee_by_emp_id_first():
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "id": {},
        "name": {},
        "emp_id": {},
        "employee_code": {},
        "active": {},
    }

    def search_read(*, model, domain, **kwargs):
        if "emp_id" in str(domain) and "2721" in str(domain):
            return [{"id": 42, "name": "Mohammad", "emp_id": "2721"}]
        return []

    adapter.search_read.side_effect = search_read
    employee, strategy = resolve_employee_by_file_id(adapter, "2721")
    assert employee is not None
    assert employee["id"] == 42
    assert strategy == "emp_id"


def test_self_vs_other_access():
    admin = CurrentUser(
        id=1,
        file_id="2721",
        name="Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
    )
    user = CurrentUser(
        id=2,
        file_id="9999",
        name="Staff",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"odoo.payroll.access"}),
    )
    assert can_access_employee_file_id(admin, "1234")
    assert can_access_employee_file_id(user, "9999")
    assert not can_access_employee_file_id(user, "1234")
    assert can_query_other_employees(admin)


def test_apply_personal_hr_scope_injects_employee():
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "id": {},
        "name": {},
        "emp_id": {},
        "active": {},
    }
    adapter.search_read.return_value = [{"id": 7, "name": "Me", "emp_id": "2721"}]

    user = CurrentUser(
        id=1,
        file_id="2721",
        name="Me",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"odoo.payroll.access"}),
    )
    scoped = apply_personal_hr_scope(
        "search_odoo",
        {
            "_scope_self": True,
            "model": "hr.payslip",
            "fields": ["name", "net_wage"],
            "filters": [],
        },
        user,
        adapter,
    )
    assert scoped["filters"] == [["employee_id", "=", 7]]
