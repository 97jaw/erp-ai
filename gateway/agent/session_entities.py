"""Active entity memory for agent sessions — employee, period, intent."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from typing import Any

_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_PAYSLIP_INTENT_RE = re.compile(
    r"\b(payslip|pay\s*slip|salary|payroll|wage|deduction|net\s+pay)\b",
    re.I,
)
_PERIOD_RE = re.compile(
    r"\b("
    + "|".join(_MONTHS)
    + r")\s*[-/]?\s*((?:20)?\d{2})\b",
    re.I,
)
_YEAR_ONLY_RE = re.compile(r"\b(20\d{2})\b")

from gateway.core.entity_gate import ConfirmedEntityRef

_entities: dict[str, dict[str, Any]] = {}

_PROJECT_INTENT_RE = re.compile(
    r"\b(expense|expenses|cost|costs|spend|budget|wo\s+amount|project\s+cost)\b",
    re.I,
)
_FLEET_INTENT_RE = re.compile(
    r"\b(vehicle|vehicles|fleet|license\s*plate|assigned\s+car|assigned\s+vehicle)\b",
    re.I,
)
_PROCUREMENT_INTENT_RE = re.compile(
    r"\b(purchase\s+order|purchase\s+orders|rfq|lpo|lpo\s+invoice|procurement)\b",
    re.I,
)
_FILE_ID_IN_PARENS_RE = re.compile(r"\((\d{3,6})\)")
_DATE_ISO_RANGE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    re.I,
)
_PROCUREMENT_DATED_TYPES = frozenset({"purchase_orders", "lpo_invoices", "invoices", "client_invoices"})


def extract_date_range_from_text(text: str) -> dict[str, str] | None:
    match = _DATE_ISO_RANGE_RE.search(text or "")
    if not match:
        return None
    return {"date_from": match.group(1), "date_to": match.group(2)}


def is_procurement_dated_query(message: str, session_id: str) -> bool:
    entities = get_entities(session_id)
    if entities.get("intent") != "procurement" and not _PROCUREMENT_INTENT_RE.search(message or ""):
        return False
    if not entities.get("project_id"):
        return False
    record_type = entities.get("procurement_record_type") or "purchase_orders"
    if record_type in UNDATED_RECORD_TYPES:
        return False
    return True


def has_procurement_date_range(session_id: str, message: str = "") -> bool:
    return has_date_range_in_session_or_message(session_id, message)


def has_financial_date_range(session_id: str, message: str = "") -> bool:
    return has_date_range_in_session_or_message(session_id, message)


def has_date_range_in_session_or_message(session_id: str, message: str = "") -> bool:
    entities = get_entities(session_id)
    if entities.get("date_from") and entities.get("date_to"):
        return True
    if extract_date_range_from_text(message):
        return True
    from gateway.clarify import _DATE_IN_QUERY_RE

    return bool(_DATE_IN_QUERY_RE.search(message or ""))


UNDATED_RECORD_TYPES = frozenset({"staff", "supervisors"})


def extract_file_id_from_text(text: str) -> str | None:
    match = _FILE_ID_IN_PARENS_RE.search(text or "")
    return match.group(1) if match else None


def get_entities(session_id: str) -> dict[str, Any]:
    return dict(_entities.get(session_id) or {})


def update_entities(session_id: str, **fields: Any) -> None:
    if not session_id:
        return
    current = _entities.setdefault(session_id, {})
    for key, value in fields.items():
        if value is not None and value != "":
            current[key] = value


def clear_financial_entities(session_id: str) -> None:
    """Remove financial report state so unrelated follow-ups do not re-run the last report."""
    bucket = _entities.get(session_id)
    if not bucket:
        return
    if bucket.get("intent") == "financial_reports":
        bucket.pop("intent", None)
    for key in (
        "financial_report_type",
        "financial_scope",
        "financial_target_move",
    ):
        bucket.pop(key, None)


def clear_documents_entities(session_id: str) -> None:
    """Drop documents wizard state when the user switches to costs, expenses, or another module."""
    bucket = _entities.get(session_id)
    if not bucket:
        return
    if bucket.get("intent") == "attachments":
        bucket.pop("intent", None)
    for key in (
        "documents_scope",
        "documents_step",
        "rfq_id",
        "agreement_id",
        "attachment_res_model",
        "attachment_res_id",
    ):
        bucket.pop(key, None)


def clear_entities(session_id: str) -> None:
    _entities.pop(session_id, None)


def extract_period_from_text(text: str) -> dict[str, Any] | None:
    """Parse 'May 2026' style period from user text."""
    match = _PERIOD_RE.search(text or "")
    if not match:
        return None
    month_name = match.group(1).lower()
    year_raw = match.group(2)
    year = int(year_raw) if len(year_raw) == 4 else 2000 + int(year_raw)
    month = _MONTHS.get(month_name)
    if not month:
        return None
    return _period_bounds(month, year)


def _period_bounds(month: int, year: int) -> dict[str, Any]:
    """Elrace payslip period: 21st of prior month through 20th of named month."""
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    date_from = date(prev_year, prev_month, 21).isoformat()
    date_to = date(year, month, min(20, monthrange(year, month)[1])).isoformat()
    month_label = date(year, month, 1).strftime("%B %Y")
    return {
        "period_month": month,
        "period_year": year,
        "period_label": month_label,
        "date_from": date_from,
        "date_to": date_to,
    }


def apply_confirmed_entities(
    session_id: str,
    confirmed: list[ConfirmedEntityRef] | None,
) -> None:
    """Persist user-confirmed entity picks (project picker, clarification card)."""
    if not session_id or not confirmed:
        return
    for ref in confirmed:
        entity_type = (ref.type or "").strip().lower()
        if entity_type in {"project", "project.project"}:
            existing = get_entities(session_id)
            if existing.get("intent") == "procurement":
                intent = "procurement"
            elif existing.get("intent") == "attachments" and (
                existing.get("documents_step") in {"scope", "target", "pick_project"}
                or existing.get("documents_scope")
            ):
                intent = "attachments"
            else:
                intent = "project_expense"
            update_entities(
                session_id,
                project_id=int(ref.id),
                project_name=str(ref.name or ""),
                intent=intent,
            )
        elif entity_type in {"employee", "hr.employee"}:
            existing = get_entities(session_id)
            file_id = extract_file_id_from_text(str(ref.name or "")) or str(ref.id)
            intent = existing.get("intent")
            if intent not in {"fleet", "payslip"}:
                intent = "fleet"
            update_entities(
                session_id,
                employee_id=int(ref.id),
                employee_name=str(ref.name or ""),
                employee_file_id=file_id,
                intent=intent,
            )


def update_entities_from_message(session_id: str, message: str) -> None:
    text = (message or "").strip()
    if not text or not session_id:
        return

    if _PAYSLIP_INTENT_RE.search(text):
        update_entities(session_id, intent="payslip")

    from gateway.agent.menu_preflight import normalize_pick_text

    norm = normalize_pick_text(text)
    if re.search(r"projects?\s*&\s*costs?", norm):
        clear_documents_entities(session_id)
        update_entities(session_id, intent="project_expense")
    elif _PROJECT_INTENT_RE.search(text):
        clear_documents_entities(session_id)
        update_entities(session_id, intent="project_expense")

    if _FLEET_INTENT_RE.search(text):
        update_entities(session_id, intent="fleet")

    if _PROCUREMENT_INTENT_RE.search(text):
        update_entities(session_id, intent="procurement", procurement_record_type="purchase_orders")

    if re.search(r"\blpo\b", text, re.I):
        update_entities(
            session_id,
            intent="procurement",
            procurement_record_type="lpo_invoices",
        )
    elif re.search(r"\brfq\b", text, re.I):
        update_entities(
            session_id,
            intent="procurement",
            procurement_record_type="purchase_orders",
        )

    from gateway.agent.menu_preflight import (
        detect_financial_report_type,
        is_financial_category_pick,
    )

    if is_financial_category_pick(text):
        update_entities(session_id, intent="financial_reports")
    report_type = detect_financial_report_type(text)
    if report_type:
        update_entities(
            session_id,
            intent="financial_reports",
            financial_report_type=report_type,
        )

    from gateway.agent.financial_clarification import (
        detect_scope_pick,
        detect_target_move_pick,
    )

    scope_pick = detect_scope_pick(text)
    if scope_pick:
        update_entities(session_id, financial_scope=scope_pick)
    target_pick = detect_target_move_pick(text)
    if target_pick:
        update_entities(session_id, financial_target_move=target_pick)

    file_id = extract_file_id_from_text(text)
    if file_id:
        update_entities(session_id, employee_file_id=file_id)

    date_range = extract_date_range_from_text(text)
    if date_range:
        update_entities(session_id, **date_range)

    period = extract_period_from_text(text)
    if period:
        update_entities(session_id, **period)

    lowered = text.lower()
    if lowered in {"payslip details", "- payslip details", "payslip", "show payslip"}:
        update_entities(session_id, intent="payslip")


def update_entities_from_tool(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
    result: Any,
) -> None:
    if not session_id or not isinstance(result, dict):
        return

    if result.get("error") or result.get("status") == "error":
        return

    if tool_name in {"get_employee_payslips", "get_payslip_detail", "get_my_payslips"}:
        update_entities(session_id, intent="payslip")
        file_id = tool_input.get("employee_file_id")
        if file_id:
            update_entities(session_id, employee_file_id=str(file_id))
        name = tool_input.get("employee_name")
        if name:
            update_entities(session_id, employee_name=str(name))

    if tool_name == "query_odoo" and tool_input.get("model") == "hr.employee":
        records = result.get("records") or []
        if len(records) == 1:
            row = records[0]
            update_entities(
                session_id,
                employee_id=int(row.get("id")),
                employee_name=str(row.get("name") or ""),
                employee_file_id=str(row.get("emp_id") or row.get("employee_code") or ""),
            )

    if tool_name == "search_entities":
        entity_type = str(tool_input.get("entity_type") or "").lower()
        candidates = result.get("candidates") or result.get("records") or []
        if entity_type in {"employee", "hr.employee"} and len(candidates) == 1:
            row = candidates[0]
            update_entities(
                session_id,
                employee_id=int(row.get("id") or row.get("entity_id") or 0) or None,
                employee_name=str(row.get("name") or row.get("label") or ""),
                employee_file_id=str(row.get("emp_id") or row.get("file_id") or ""),
            )
        if entity_type == "project" and len(candidates) == 1:
            row = candidates[0]
            updates: dict[str, Any] = {
                "project_id": int(row.get("id") or row.get("entity_id") or 0) or None,
                "project_name": str(row.get("name") or row.get("label") or ""),
            }
            entities = get_entities(session_id)
            if entities.get("intent") != "financial_reports":
                updates["intent"] = "project_expense"
            update_entities(session_id, **updates)

    if tool_name in {
        "get_project_expense_summary",
        "get_project_expense_breakdown",
        "compare_project_expenses",
        "get_project_profile",
        "get_project_records",
        "get_project_activity",
    }:
        project_id = tool_input.get("project_id")
        if project_id:
            update_entities(
                session_id,
                project_id=int(project_id),
                intent="project_expense",
            )
        project_name = tool_input.get("project_name")
        if project_name:
            update_entities(session_id, project_name=str(project_name))

    if tool_name == "search_fleet_vehicles":
        vehicles = result.get("vehicles") or []
        if vehicles:
            update_entities(session_id, intent="fleet")
        if result.get("employee_file_id"):
            update_entities(session_id, employee_file_id=str(result["employee_file_id"]))
        if result.get("employee_name"):
            update_entities(session_id, employee_name=str(result["employee_name"]))

    if tool_name in {"get_purchase_orders", "get_project_records"}:
        update_entities(session_id, intent="procurement")

    if tool_name == "list_attachments":
        update_entities(session_id, intent="attachments")
        if tool_input.get("project_id"):
            update_entities(session_id, project_id=int(tool_input["project_id"]))
        if tool_input.get("agreement_id"):
            update_entities(session_id, agreement_id=int(tool_input["agreement_id"]))
        if tool_input.get("rfq_id"):
            update_entities(session_id, rfq_id=int(tool_input["rfq_id"]))

    employee = result.get("employee")
    if isinstance(employee, dict):
        update_entities(
            session_id,
            employee_id=employee.get("id"),
            employee_name=str(employee.get("name") or ""),
            employee_file_id=str(employee.get("emp_id") or employee.get("file_id") or ""),
        )


def enrich_payroll_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id:
        return enriched

    entities = get_entities(session_id)
    payroll_tools = {
        "get_payslip_detail",
        "get_employee_payslips",
        "get_my_payslips",
    }
    if tool_name not in payroll_tools:
        return enriched

    if not enriched.get("employee_file_id") and entities.get("employee_file_id"):
        enriched["employee_file_id"] = entities["employee_file_id"]
    if not enriched.get("employee_name") and entities.get("employee_name"):
        enriched["employee_name"] = entities["employee_name"]

    if tool_name == "get_payslip_detail":
        if not enriched.get("date_from") and entities.get("date_from"):
            enriched["date_from"] = entities["date_from"]
        if not enriched.get("date_to") and entities.get("date_to"):
            enriched["date_to"] = entities["date_to"]
        if entities.get("intent") == "payslip" and not enriched.get("detail_type"):
            enriched.setdefault("detail_type", "full")

    return enriched


def enrich_project_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id:
        return enriched

    from gateway.tools.project_activity import PROJECT_ACTIVITY_TOOL_NAMES
    from gateway.tools.project_expense import PROJECT_EXPENSE_TOOL_NAMES
    from gateway.tools.project_profile import PROJECT_PROFILE_TOOL_NAMES
    from gateway.tools.project_records import PROJECT_RECORDS_TOOL_NAMES

    project_tools = (
        PROJECT_EXPENSE_TOOL_NAMES
        | PROJECT_PROFILE_TOOL_NAMES
        | PROJECT_RECORDS_TOOL_NAMES
        | PROJECT_ACTIVITY_TOOL_NAMES
        | frozenset({"get_project_financial_data"})
    )
    if tool_name not in project_tools:
        return enriched

    entities = get_entities(session_id)
    if not enriched.get("project_id") and entities.get("project_id"):
        enriched["project_id"] = entities["project_id"]
    if not enriched.get("project_name") and entities.get("project_name"):
        enriched["project_name"] = entities["project_name"]
    return enriched


def enrich_fleet_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id or tool_name != "search_fleet_vehicles":
        return enriched

    entities = get_entities(session_id)
    if not enriched.get("employee_file_id") and entities.get("employee_file_id"):
        enriched["employee_file_id"] = str(entities["employee_file_id"])
    if not enriched.get("employee_name") and entities.get("employee_name"):
        enriched["employee_name"] = str(entities["employee_name"])
    return enriched


def enrich_procurement_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id:
        return enriched

    entities = get_entities(session_id)
    if tool_name == "get_purchase_orders":
        if not enriched.get("project_id") and entities.get("project_id"):
            enriched["project_id"] = entities["project_id"]
        if not enriched.get("project_name") and entities.get("project_name"):
            enriched["project_name"] = entities["project_name"]
    if tool_name == "get_project_records":
        if not enriched.get("project_id") and entities.get("project_id"):
            enriched["project_id"] = entities["project_id"]
        if not enriched.get("record_type"):
            intent = entities.get("record_type") or entities.get("procurement_record_type")
            if intent:
                enriched["record_type"] = intent
            elif entities.get("intent") == "procurement":
                enriched.setdefault("record_type", "purchase_orders")
        if not enriched.get("date_from") and entities.get("date_from"):
            enriched["date_from"] = entities["date_from"]
        if not enriched.get("date_to") and entities.get("date_to"):
            enriched["date_to"] = entities["date_to"]
    return enriched


def enrich_attachment_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id or tool_name != "list_attachments":
        return enriched

    entities = get_entities(session_id)
    if not enriched.get("project_id") and entities.get("project_id"):
        enriched["project_id"] = entities["project_id"]
    if not enriched.get("agreement_id") and entities.get("agreement_id"):
        enriched["agreement_id"] = entities["agreement_id"]
    if not enriched.get("rfq_id") and entities.get("rfq_id"):
        enriched["rfq_id"] = entities["rfq_id"]
    return enriched


def enrich_financial_tool_input(
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    from gateway.date_utils import DATE_RANGE_TOOLS, enforce_date_range

    if tool_name not in DATE_RANGE_TOOLS:
        return enriched
    return enforce_date_range(tool_name, enriched)


def build_entity_context_prompt(session_id: str) -> str:
    entities = get_entities(session_id)
    if not entities:
        return ""

    lines: list[str] = []
    if entities.get("employee_name"):
        line = f"- Active employee: {entities['employee_name']}"
        if entities.get("employee_id"):
            line += f" (hr.employee ID {entities['employee_id']})"
        if entities.get("employee_file_id"):
            line += f" — File ID / emp_id {entities['employee_file_id']}"
        lines.append(line)
    if entities.get("period_label"):
        lines.append(f"- Active payroll period: {entities['period_label']}")
        if entities.get("date_from") and entities.get("date_to"):
            lines.append(
                f"  Use date_from={entities['date_from']}, date_to={entities['date_to']} "
                "for payslip tools."
            )
    if entities.get("intent") == "payslip":
        lines.append("- User intent: payslip / payroll for the active employee and period.")

    if entities.get("project_name") or entities.get("project_id"):
        line = "- Active project:"
        if entities.get("project_name"):
            line += f" {entities['project_name']}"
        if entities.get("project_id"):
            line += f" (project_id={entities['project_id']})"
        lines.append(line)
    if entities.get("intent") == "project_expense":
        lines.append(
            "- User intent: project costs / expenses for the active project. "
            "Call get_project_expense_summary or breakdown with project_id — "
            "then render_visualization with the figures."
        )

    if entities.get("intent") == "fleet":
        lines.append(
            "- User intent: fleet / assigned vehicle. "
            "Call search_fleet_vehicles with employee_file_id and/or employee_name — "
            "show vehicle plate, model, project, location."
        )

    if entities.get("intent") == "procurement":
        record_type = entities.get("procurement_record_type") or "purchase_orders"
        lines.append(
            "- User intent: purchase orders / LPO / RFQ. "
            f"Call get_project_records(project_id, record_type={record_type}) when a project is active. "
            "For client-level PO lists use get_purchase_orders. "
            "Default period: last 3 months unless user says all time — then omit date filters."
        )

    if entities.get("intent") == "attachments":
        lines.append(
            "- User intent: documents / attachments / files. "
            "Call list_attachments with project_id (and include_agreement when relevant). "
            "For RFQ files pass rfq_id; for any record use res_model + res_id. "
            "Do NOT use get_project_records for file downloads."
        )

    if entities.get("intent") == "financial_reports":
        report_type = entities.get("financial_report_type") or "unspecified"
        lines.append(
            "- User intent: financial reports. "
            f"Active report type: {report_type}. "
            "Do NOT show the top-level welcome menu or module picker again. "
            "Call get_trial_balance, get_financial_report, get_general_ledger, or "
            "get_partner_ageing with date_from/date_to immediately — show real figures."
        )
        if entities.get("date_from") and entities.get("date_to"):
            lines.append(
                f"  Use date_from={entities['date_from']}, date_to={entities['date_to']}."
            )

    if not lines:
        return ""

    return (
        "\n\nACTIVE SESSION CONTEXT (reuse — do not re-ask if already known):\n"
        + "\n".join(lines)
        + "\n- When user says 'that', 'his', 'her', 'payslip details', or picks a payslip chip, "
        "apply this context.\n"
        + "- Call get_payslip_detail (preferred) or get_employee_payslips — "
        "NEVER query_odoo hr.payslip without employee_id + period filters.\n"
    )


def domain_has_employee_filter(domain: list[Any]) -> bool:
    for clause in domain or []:
        if not isinstance(clause, (list, tuple)) or len(clause) < 3:
            continue
        field = str(clause[0])
        if field in {"employee_id", "employee_id.name"}:
            return True
    return False
