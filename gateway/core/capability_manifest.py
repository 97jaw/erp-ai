"""Explicit inventory of available, unavailable, and coming-soon capabilities.

Enables honest failure handling by letting the agent know what it can and
cannot do before attempting tool execution.
"""

from dataclasses import dataclass


@dataclass
class Capability:
    """A single capability entry in the manifest."""

    code: str
    description: str
    alternative: str | None = None
    roadmap: str | None = None
    eta: str | None = None


@dataclass
class CapabilityManifest:
    """Explicit inventory of what's available and what isn't."""

    available: list[Capability]
    unavailable: list[Capability]
    coming_soon: list[Capability]

    def can_do(self, capability_code: str) -> bool:
        """Return True if the capability is currently available."""
        return capability_code in {capability.code for capability in self.available}

    def status_of(self, capability_code: str) -> str:
        """Return availability status for a capability code."""
        for capability in self.available:
            if capability.code == capability_code:
                return "available"
        for capability in self.coming_soon:
            if capability.code == capability_code:
                return "coming_soon"
        for capability in self.unavailable:
            if capability.code == capability_code:
                return "unavailable"
        return "unknown"

    def summary(self) -> str:
        """Format manifest for inclusion in Claude system prompt."""
        return f"""
WHAT YOU CAN DO:
{self._format_list(self.available)}

WHAT YOU CANNOT DO (be honest if asked):
{self._format_list(self.unavailable)}

WHAT'S COMING SOON (mention when relevant):
{self._format_list(self.coming_soon)}

CRITICAL RULES:
- For ANY read/data question about Odoo (HR, payroll, inventory, purchases,
  sales, fleet, timesheets, or any installed model): attempt query_odoo or
  aggregate_odoo. Use introspect_odoo_schema when unsure of the model.
- If query_odoo returns no rows: say "no data found" honestly — do not refuse
  upfront because a module was previously marked unavailable.
- If asked about an "unavailable" capability (writes or non-ERP):
  → State honestly what you cannot do (read-only / ERP-only)
  → DO NOT FABRICATE FAKE ERRORS like "database issue"
- If asked about "coming_soon" capability:
  → Acknowledge it's in development
  → Provide ETA if known
  → Suggest workaround when possible
"""

    def tools_summary(self) -> str:
        """Return gateway tool names available for strategy planning prompts."""
        return (
            "query_odoo, aggregate_odoo, introspect_odoo_schema, "
            "get_financial_report, get_project_expenses, get_project_financial_data, "
            "get_project_expense_summary, get_project_expense_breakdown, compare_project_expenses, "
            "get_general_ledger, get_trial_balance, get_partner_ageing, get_partner_ledger, "
            "get_projects_summary, search_odoo, group_and_aggregate"
        )

    def _format_list(self, capabilities: list[Capability]) -> str:
        """Format capability entries for prompt inclusion."""
        lines: list[str] = []
        for capability in capabilities:
            line = f"- {capability.code}: {capability.description}"
            if capability.alternative:
                line += f" (alternative: {capability.alternative})"
            if capability.roadmap:
                line += f" (roadmap: {capability.roadmap})"
            if capability.eta:
                line += f" (eta: {capability.eta})"
            lines.append(line)
        return "\n".join(lines) if lines else "- None"


CAPABILITY_MANIFEST = CapabilityManifest(
    available=[
        Capability(
            "universal.odoo_read",
            "Read any Odoo model via query_odoo and aggregate_odoo",
        ),
        Capability("financial.pandl", "Profit & Loss reports"),
        Capability("financial.balance_sheet", "Balance Sheet"),
        Capability("financial.cash_flow", "Cash Flow Statement"),
        Capability("financial.trial_balance", "Trial Balance"),
        Capability("financial.general_ledger", "General Ledger"),
        Capability("project.financials", "Project financial data"),
        Capability("project.expense_summary", "Project expense summary (mobile API KPIs)"),
        Capability("project.expense_breakdown", "Project GL expense breakdown"),
        Capability("project.expense_compare", "Multi-project expense comparison"),
        Capability("project.search", "Project search by name/code"),
        Capability("partner.search", "Customer/Vendor search"),
        Capability("partner.ageing", "Receivables/Payables ageing"),
        Capability("partner.ledger", "Partner transaction history"),
        Capability("hr.employees", "Employee directory and headcount reads"),
        Capability("hr.payslips", "Payslip reads via query_odoo"),
        Capability("hr.payslip_detail", "Payslip salary lines, deductions, and project distribution"),
        Capability("hr.requests", "Employee workflow requests (leave, loan, transfer, termination)"),
        Capability("hr.request_detail", "HR request validation chain, leave dates, and approval status"),
        Capability("hr.terminations", "Termination and separation counts from employee.requests"),
        Capability("hr.attendance", "Attendance record reads"),
        Capability("hr.leave_balance", "Leave balance reads"),
        Capability("inventory.stock", "Inventory and stock level reads"),
        Capability("purchase.read", "Purchase orders and vendor data reads"),
        Capability("sales.read", "Sales orders and quotation reads"),
        Capability("crm.opportunities", "CRM opportunity reads"),
        Capability("fleet.read", "Fleet vehicle reads with driver, employee link, project, and location"),
        Capability("timesheet.read", "Timesheet and analytic line reads"),
        Capability("fsm.read", "Field service reads"),
        Capability("reports.generate_pdf", "PDF report generation"),
        Capability("reports.generate_excel", "Excel export"),
        Capability("voice.input", "Voice query input"),
        Capability("voice.output", "Voice response output"),
        Capability("language.arabic", "Arabic language support"),
        Capability("language.english", "English language support"),
    ],
    unavailable=[
        Capability(
            "write.create_record",
            "Create new Odoo records (invoices, orders, employees, etc.)",
            alternative="Use Odoo directly to create records",
        ),
        Capability(
            "write.update_record",
            "Update or modify existing Odoo records",
            alternative="Use Odoo directly to edit records",
        ),
        Capability(
            "write.delete_record",
            "Delete or archive Odoo records",
            alternative="Use Odoo directly",
        ),
        Capability(
            "write.approve_transactions",
            "Approve, post, cancel, or validate transactions",
            alternative="Use Odoo approval workflows",
        ),
        Capability(
            "non_erp.weather",
            "Weather forecasts and non-business external data",
            alternative="Use a weather service or app",
        ),
        Capability(
            "non_erp.web_browsing",
            "General web browsing and external sites",
            alternative="Use a web browser",
        ),
        Capability(
            "non_erp.general_knowledge",
            "General knowledge unrelated to Elrace ERP data",
            alternative="I'm an ERP assistant for Elrace Odoo data",
        ),
    ],
    coming_soon=[
        Capability("integrations.outlook_email", "Outlook email sync", eta="Q2 2026"),
        Capability("integrations.whatsapp", "WhatsApp delivery", eta="Q3 2026"),
        Capability("dashboards.custom", "Custom dashboards", eta="Q3 2026"),
        Capability("forecasting.cash_flow", "Cash flow forecasting", eta="Q4 2026"),
    ],
)
