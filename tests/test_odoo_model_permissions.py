from admin.auth.principal import CurrentUser
from admin.rbac.model_permissions import permission_for_model
from admin.rbac.tool_permissions import check_tool_allowed, permission_for_tool


def test_permission_for_model_hr_and_payroll() -> None:
    assert permission_for_model("hr.employee") == "odoo.hr.access"
    assert permission_for_model("hr.payslip") == "odoo.payroll.access"
    assert permission_for_model("project.project") == "odoo.projects.access"
    assert permission_for_model("account.analytic.line") == "odoo.timesheets.access"


def test_permission_for_tool_search_odoo() -> None:
    assert (
        permission_for_tool("search_odoo", {"model": "hr.employee"})
        == "odoo.hr.access"
    )
    assert (
        permission_for_tool("search_odoo", {"model": "hr.payslip.run"})
        == "odoo.payroll.access"
    )


def test_super_admin_bypasses_odoo_model_check() -> None:
    user = CurrentUser(
        id=1,
        file_id="2721",
        name="Super",
        language="en",
        is_super_admin=True,
        is_active=True,
        permissions=frozenset(),
    )
    assert check_tool_allowed(user, "search_odoo", {"model": "hr.payslip"}) is None


def test_odoo_full_access_bypasses_model_check() -> None:
    user = CurrentUser(
        id=2,
        file_id="u2",
        name="Power",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"odoo.full_access"}),
    )
    assert check_tool_allowed(user, "search_odoo", {"model": "hr.payslip"}) is None


def test_hr_access_allows_payslip_tools() -> None:
    user = CurrentUser(
        id=4,
        file_id="hr1",
        name="HR",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"odoo.hr.access"}),
    )
    assert check_tool_allowed(user, "get_my_payslips") is None
    assert check_tool_allowed(user, "list_recent_payslips") is None
    assert check_tool_allowed(user, "search_odoo", {"model": "hr.payslip"}) is None


def test_guest_denied_hr_without_permission() -> None:
    user = CurrentUser(
        id=3,
        file_id="guest",
        name="Guest",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"reports.pandl.view"}),
    )
    err = check_tool_allowed(user, "search_odoo", {"model": "hr.employee"})
    assert err and "odoo.hr.access" in err
