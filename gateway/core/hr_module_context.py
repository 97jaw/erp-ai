"""Elrace HR module context for Claude system prompt (Phase M2).

Static domain knowledge — no runtime tool changes. Claude composes
query_odoo / aggregate_odoo using this map.
"""

HR_MODULE_PROMPT_SECTION = """
=== ELRACE HR MODULE ===

EMPLOYEE STRUCTURE — TWO CLASSES:
  Elrace has 3000+ employees split into TWO classes:
    - LABOR (workers): emp_type="labor", is_labor=True,
      paid via labor_payroll_engine, has timesheet_cost field
    - STAFF (managers/admin): emp_type="staff", is_labor=False,
      paid via staff_payroll_engine

  When user asks "employees" generically → include BOTH.
  When asked about "labor"/"workers" → filter is_labor=True.
  When asked about "staff"/"managers" → filter is_labor!=True.

hr.employee KEY FIELDS:
  Identity: name, emp_id, identification_id (Emirates ID),
            passport_id, mol_number
  Type: emp_type, is_labor, grade
  Org: department_id, section_id, branch_id, job_id, job_title,
       parent_id (manager), coach_id (foreman)
  Project: project_id, project_id_store, current_forman,
           projects_manager_id, working_facility, analytic_account_id
  Cost: timesheet_cost (per-hour AED cost)
  Status: active, state, resigned, fired, resign_date,
          joining_date, labour_joining_date
  Compliance: visa_expire, labour_card_expiry_date,
              passport_expiry_date, has_missing_required_docs,
              missing_required_doc_names
  Sick leave tracking (UAE 90-day quota):
    sick_leave_full_paid_remaining (15 days/yr at 100%)
    sick_leave_half_paid_remaining (30 days/yr at 50%)
    sick_leave_unpaid_remaining (45 days/yr at 0%)
  Mobile/device: mobile_access, device_binding_enabled,
                 face_enrollment_status

employee.requests — THE HR WORKFLOW ENGINE:
  27 request types stored in request.type model.
  status flow: draft → first_approver_id → second_approver_id
               → 'approve' or 'refuse'
  is_approve=True when fully approved.

  COMMON REQUEST TYPES (by request_type field):
    "leave" → Annual, Sick, Emergency, JM, TP, Encashment
    "resignation" / "termination" / "clearance"
    "transfer" / "promotion" / "increment"
    "recruitment" / "effective_date"
    "advance_salary" / "loan"
    "passport_request" / "sim_card_request" / "car_rent_request"
    "salary_details" (change salary)
    "certificate" (salary certificate)

  Some are class-specific:
    is_labor_only=True (e.g. Passport Request)
    is_staff_only=True (e.g. Sim Card)

hr.attendance — PRE-PROCESSED:
  x_attendance_type is the master field:
    "present" → actual work day
    "annual" → annual leave
    "sick" → sick leave
    "absent" → unauthorized absence (x_is_absent=True)
    "temp_permission" → partial day (x_tp_hours)
    "job_mission" → JM hours (x_jm_hours)
    "work_compensation" → comp day

  CRITICAL RULE: Always filter by x_attendance_type.
    worked_hours alone is misleading — leave entries can show
    480 or 720 worked_hours (days×hours) which are NOT real work.

    Real work hours: x_attendance_type="present"
    Real absences: x_is_absent=True

  x_attendance_month = pre-aggregated key like "2026-04"
    (use for fast monthly grouping)
  x_is_auto_generated=True for system-created entries
    (e.g. leave-converted-to-attendance)

ORGANIZATION HIERARCHY:
  parent_id = direct line manager
  coach_id = foreman (mostly for labor)
  branch_manager_id, project_manager_id, projects_manager_id
  department_id → hr.department.manager_id

COMPLIANCE QUERY PATTERNS:
  "visas expiring in N days":
    hr.employee where visa_expire between today and today+N,
    active=True

  "expired labour cards":
    hr.employee where labour_card_expiry_date < today,
    active=True

  "employees with missing documents":
    hr.employee where has_missing_required_docs=True,
    show missing_required_doc_names

PROJECT ASSIGNMENT:
  project_id or project_id_store = current/last project
  For ACTUAL labor cost on project, prefer
  hr.payslip.cost.allocation (covered in payroll section).

=== HR QUERY ROUTING (MANDATORY) ===

Pick the correct Odoo model FIRST — do NOT default every HR question to
hr.employee headcount grouped by department.

HEADcount / DIRECTORY:
  Total employees, per department, biggest department, employees in Civil:
    → aggregate_odoo on hr.employee (active=True)
  Labor vs staff split:
    → aggregate_odoo on hr.employee grouped by is_labor
    (or two counts: is_labor=True vs is_labor=False)
  Employee details by person name:
    → query_odoo hr.employee with name ilike — NOT a project lookup
  Managers in company:
    → query hr.department manager_id and/or hr.employee with management jobs
  Foremen list:
    → query hr.employee where coach_id is used OR job_title ilike foreman
    OR employees referenced as coach_id on other employees

STRUCTURE:
  List all departments / Civil department head:
    → query_odoo hr.department (manager_id = department head)
  Branches we have:
    → query branch model OR aggregate hr.employee by branch_id

HR REQUESTS (leave, resignation, transfer, loan, promotion):
  → query_odoo employee.requests — NEVER hr.employee alone
  Pending: status in (draft, submit, submitted) or not is_approve
  Approved: is_approve=True or status=approve
  Filter request_type / request_type_id for resignation, transfer, loan, promotion, leave
  Unresolved requests: employee.requests not in approved/refused final state

ATTENDANCE:
  → query_odoo or aggregate_odoo on hr.attendance (NOT hr.employee)
  ALWAYS filter x_attendance_type AND date (check_in / x_attendance_month)
  Today count: check_in date = today, x_attendance_type=present
  Absent yesterday: x_attendance_type=absent OR x_is_absent=True, date=yesterday
  On leave today: x_attendance_type in (annual, sick) for today
  Work hours by department this month:
    aggregate hr.attendance where x_attendance_type=present,
    group by employee department (via employee_id.department_id)

COMPLIANCE:
  Visas / labour cards / passports / EID / missing documents:
    → query_odoo hr.employee with the specific compliance date/boolean filters
    (visa_expire, labour_card_expiry_date, passport_expiry_date,
     identification_id, has_missing_required_docs)

CROSS-MODULE:
  Who works on project X:
    → query_odoo hr.employee where project_id = resolved project id
    (NOT get_project_profile unless user asked project header only)
  Employee assigned vehicle:
    → resolve employee, then query fleet.vehicle / employee vehicle link
  Employee project history:
    → employee.requests transfers OR project assignment fields on hr.employee
  Department headcount by project:
    → aggregate hr.employee by project_id and department_id

ANTI-PATTERNS (never do these):
  - Do NOT answer leave/attendance/compliance from generic hr.employee name lists
  - Do NOT route person-name HR queries through project entity confirmation
  - Do NOT use worked_hours without x_attendance_type filter
  - Do NOT use group_and_aggregate when aggregate_odoo with group_by suffices

=== END HR CONTEXT ===
"""
