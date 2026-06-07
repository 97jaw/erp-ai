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
- If asked about an "unavailable" capability:
  → State honestly it's not available
  → Suggest alternative if any
  → Offer to track when ready
  → DO NOT FABRICATE FAKE ERRORS like "database issue"

- If asked about "coming_soon" capability:
  → Acknowledge it's in development
  → Provide ETA if known
  → Suggest workaround
"""

    def tools_summary(self) -> str:
        """Return gateway tool names available for strategy planning prompts."""
        return (
            "get_financial_report, get_project_expenses, get_project_financial_data, "
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
        Capability("financial.pandl", "Profit & Loss reports"),
        Capability("financial.balance_sheet", "Balance Sheet"),
        Capability("financial.cash_flow", "Cash Flow Statement"),
        Capability("financial.trial_balance", "Trial Balance"),
        Capability("financial.general_ledger", "General Ledger"),
        Capability("project.financials", "Project financial data"),
        Capability("project.search", "Project search by name/code"),
        Capability("partner.search", "Customer/Vendor search"),
        Capability("partner.ageing", "Receivables/Payables ageing"),
        Capability("partner.ledger", "Partner transaction history"),
        Capability("reports.generate_pdf", "PDF report generation"),
        Capability("reports.generate_excel", "Excel export"),
        Capability("voice.input", "Voice query input"),
        Capability("voice.output", "Voice response output"),
        Capability("language.arabic", "Arabic language support"),
        Capability("language.english", "English language support"),
    ],
    unavailable=[
        Capability(
            "hr.payslips",
            "Payslip access",
            alternative="Use the HR portal directly at hr.elrace.com",
            roadmap="Q3 2026",
        ),
        Capability(
            "hr.attendance",
            "Attendance records",
            alternative="Use HR portal",
            roadmap="Q3 2026",
        ),
        Capability(
            "hr.leave_balance",
            "Leave balance",
            alternative="Use HR portal",
            roadmap="Q3 2026",
        ),
        Capability(
            "inventory.stock",
            "Inventory levels",
            alternative="Use Odoo Inventory module directly",
            roadmap="Q4 2026",
        ),
        Capability(
            "crm.opportunities",
            "Sales opportunities",
            alternative="Use CRM module",
            roadmap="Q4 2026",
        ),
        Capability(
            "write.create_invoice",
            "Create invoices",
            alternative="Use Odoo directly",
            roadmap="Q4 2026",
        ),
        Capability(
            "write.approve_payments",
            "Approve payments",
            alternative="Use Odoo approval flow",
            roadmap="2027",
        ),
    ],
    coming_soon=[
        Capability("integrations.outlook_email", "Outlook email sync", eta="Q2 2026"),
        Capability("integrations.whatsapp", "WhatsApp delivery", eta="Q3 2026"),
        Capability("dashboards.custom", "Custom dashboards", eta="Q3 2026"),
        Capability("forecasting.cash_flow", "Cash flow forecasting", eta="Q4 2026"),
    ],
)
