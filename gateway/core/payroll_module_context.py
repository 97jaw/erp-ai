"""Elrace Payroll module context for Claude system prompt (Phase M6).

Static domain knowledge — no runtime tool changes. Claude composes
query_odoo / aggregate_odoo using this map.
"""

PAYROLL_MODULE_PROMPT_SECTION = """
=== ELRACE PAYROLL MODULE ===

TWO PAYROLL ENGINES — LABOR vs STAFF:
  Payslips store amounts in TWO snapshot families:
    labor_snapshot_* fields → used when emp_type="labor"
    staff_snapshot_* fields → used when emp_type="staff"

  When computing total payroll, MUST sum BOTH:
    total = labor_snapshot_total_salary + staff_snapshot_total_salary

  Or filter by emp_type and use the matching snapshot.

hr.payslip — THE PAYSLIP RECORD:
  Identity: name (e.g. "Salary Slip of Mohamed for April-2026"),
            number (e.g. "SLIP/99079"), employee_id, contract_id
  Batch: payslip_run_id → hr.payslip.run (monthly batch)
  Period: date_from, date_to (typically 21st prev to 20th current)
  State: draft → verify → finance → paid

  Net amount: net_salary (final payable)
  Snapshot totals (by class):
    labor_snapshot_total_salary
    staff_snapshot_total_salary

  Deductions: fine, advance, pension, unemployment_insurance,
              total_deductions (usually negative sum)

  Overtime breakdown:
    weekend_ot_days, weekend_ot_hours (150% rate typical)
    normal_ot_days, normal_ot_hours (125% rate)
    holiday_ot_days, holiday_ot_hours (200% rate)
    total_over_time (aggregated)

  Sick leave breakdown (UAE labor law):
    sick_leave_full_paid_days/amount (100% paid)
    sick_leave_half_paid_days/amount (50% paid)
    sick_leave_unpaid_days/amount (0% paid)

  Project linkage:
    project_id (if dedicated to single project)
    project_days
    move_id → account.move (accounting journal entry)
    operating_unit_id

hr.payslip.worked.days — PER-CODE BREAKDOWN:
  Each row: payslip_id × code × days × hours × amount

  CODE values:
    JM       → Job Mission (off-site)
    ANNUAL   → Annual leave (compensated in leave salary)
    SL_FULL  → Sick leave full paid
    SL_HALF  → Sick leave half paid
    LEAVE700 → Emergency leave
    TP       → Temporary permission

  Use for queries like:
    "annual leave salary paid this year"
    "total JM hours per employee"
    "sick leave usage by department"

hr.payslip.run — MONTHLY BATCH:
  state: draft, verify, close
  date_start, date_end
  Filter by date_start year/month for "April 2026 batch" queries

⭐ THE FLAGSHIP TABLE — hr.payslip.cost.allocation ⭐
  Pre-computed labor cost allocation per project per month.
  This is the SINGLE source for cross-module project labor cost.

  Fields:
    employee_id, project_id, month (str "1"-"12"), year (str)
    allocation (0.0-1.0 = % of employee's time on this project)
    total_salary (full month salary)
    amount = total_salary × allocation (allocated portion)
    agreement_id (contract link), partner_id (client)
    operating_unit_id, batch_id

  USE THIS TABLE for any "labor cost for project" query.

  Pattern:
    "labor cost for Villa 34 this month":
      aggregate_odoo("hr.payslip.cost.allocation",
        [["project_id","=",15157],
         ["month","=","6"], ["year","=","2025"]],
        [], ["amount:sum"])

    "top projects by labor cost":
      aggregate_odoo("hr.payslip.cost.allocation",
        [["year","=","2025"]],
        ["project_id"], ["amount:sum"])
      sort by amount, take top N

    "employee labor cost breakdown for Villa 34":
      aggregate by employee_id for the project

PERMISSIONS — SENSITIVE DATA:
  hr.payslip, hr.contract individual records are SENSITIVE.
  - Super admin (level>=100): full access including wages
  - Top mgmt (level>=70): aggregate totals OK, no individual wages
  - Below 70: redacted (***restricted***) per existing rules

  hr.payslip.cost.allocation aggregates are LESS sensitive
  (project totals, not individual wages) — top mgmt can see.

=== END PAYROLL CONTEXT ===
"""
