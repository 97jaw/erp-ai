from __future__ import annotations

import re
from typing import Any

from gateway.quality_formatting import format_currency, format_percentage, humanize_group_label

_PERIOD_IN_QUERY_RE = re.compile(
    r"\b("
    r"this\s+year|last\s+year|ytd|year\s+to\s+date|"
    r"this\s+month|last\s+month|"
    r"q[1-4]|quarter|"
    r"last\s+\d+\s+months?"
    r")\b",
    re.IGNORECASE,
)

_LEGACY_PERIOD_PHRASE = "for the selected period"


def user_asked_for_calendar_period(message: str = "") -> bool:
    """Return True when the user mentioned a date range in the query."""
    return bool(_PERIOD_IN_QUERY_RE.search(message or ""))


def is_legacy_period_expense_text(text: str = "") -> bool:
    """Detect generic legacy synthesizer copy that should be replaced."""
    lowered = (text or "").lower()
    return _LEGACY_PERIOD_PHRASE in lowered


def narrate_project_expense_summary(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Build executive summary text for mobile project expense payloads."""
    project_name = payload.get("project_name") or "Project"
    total = float(payload.get("total_expenses") or 0)
    wo_amount = float(payload.get("wo_amount") or 0)
    spend_status = payload.get("spend_status")
    status_label = payload.get("status_label")
    spend_pct_raw = payload.get("spend_percent_of_wo")
    spend_pct = float(spend_pct_raw) if spend_pct_raw is not None else None

    if spend_status == "no_budget_assigned":
        status = status_label or "no W.O budget assigned"
        if language == "ar":
            lead = (
                f"{project_name}: مصروفات مسجلة بقيمة {format_currency(total)}، "
                "لكن لا يوجد W.O معين في النظام، لذا لا يمكن عرض نسبة الإنفاق أو حالة الميزانية."
            )
        else:
            lead = (
                f"{project_name} has {format_currency(total)} in recorded expenses, "
                "but no W.O budget is assigned in the system, so no spend percentage "
                "or budget status is available."
            )
    elif spend_status == "no_data":
        if language == "ar":
            lead = f"وجدت {project_name} لكن لا توجد مصروفات مسجلة لها بعد."
        else:
            lead = f"I found {project_name} but there are no expenses recorded for it yet."
    elif payload.get("is_over_budget") or spend_status == "over_budget":
        status = status_label or "over budget"
        if language == "ar":
            lead = (
                f"{project_name}: إجمالي المصروف {format_currency(total)} "
                f"({format_percentage(spend_pct or 0)} من W.O {format_currency(wo_amount)}). "
                f"الحالة: {status}."
            )
        else:
            lead = (
                f"{project_name}: total spend is {format_currency(total)} "
                f"({format_percentage(spend_pct or 0)} of W.O {format_currency(wo_amount)}). "
                f"Status: {status}."
            )
    elif spend_pct is not None and spend_pct > 95:
        status = "near the W.O limit"
        if language == "ar":
            lead = (
                f"{project_name}: إجمالي المصروف {format_currency(total)} "
                f"({format_percentage(spend_pct)} من W.O {format_currency(wo_amount)}). "
                f"الحالة: {status}."
            )
        else:
            lead = (
                f"{project_name}: total spend is {format_currency(total)} "
                f"({format_percentage(spend_pct)} of W.O {format_currency(wo_amount)}). "
                f"Status: {status}."
            )
    elif spend_pct is not None:
        status = status_label or "on track"
        if language == "ar":
            lead = (
                f"{project_name}: إجمالي المصروف {format_currency(total)} "
                f"({format_percentage(spend_pct)} من W.O {format_currency(wo_amount)}). "
                f"الحالة: {status}."
            )
        else:
            lead = (
                f"{project_name}: total spend is {format_currency(total)} "
                f"({format_percentage(spend_pct)} of W.O {format_currency(wo_amount)}). "
                f"Status: {status}."
            )
    else:
        if language == "ar":
            lead = f"{project_name}: إجمالي المصروف {format_currency(total)}."
        else:
            lead = f"{project_name}: total spend is {format_currency(total)}."

    top_expenses = payload.get("top_expenses") or []
    trade_bits: list[str] = []
    for item in top_expenses[:3]:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("label") or "Other"
        amount = float(item.get("amount") or 0)
        percent = item.get("percent")
        if percent is not None:
            trade_bits.append(f"{name} ({format_currency(amount)}, {format_percentage(float(percent))})")
        else:
            trade_bits.append(f"{name} ({format_currency(amount)})")

    parts = [lead]
    if trade_bits:
        if language == "ar":
            parts.append(f"أبرز الفئات: {', '.join(trade_bits)}.")
        else:
            parts.append(f"Top trade categories: {', '.join(trade_bits)}.")

    context_message = user_message or str(payload.get("project_name") or "")
    if user_asked_for_calendar_period(context_message):
        if language == "ar":
            parts.append(
                "ملاحظة: هذا ملخص مصروفات المشروع الكامل (حسب W.O) كما في تطبيق Odoo — "
                "وليس مفلتراً حسب السنة أو الفترة."
            )
        else:
            parts.append(
                "Note: this is the full project expense summary (W.O-based), matching the Odoo "
                "mobile view — not filtered to a calendar period."
            )

    return " ".join(parts)


def narrate_project_expense_breakdown(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Build narrative for GL expense breakdown (MG → SG → Account)."""
    del user_message
    project_name = payload.get("project_name") or "Project"
    currency = payload.get("currency") or "AED"
    grand_total = float(payload.get("grand_total") or 0)
    groups = payload.get("groups") or []
    group_count = int(payload.get("group_count") or len(groups))

    if language == "ar":
        lead = (
            f"{project_name}: تفصيل المصروفات على مستوى الحسابات "
            f"{format_currency(grand_total)} عبر {group_count} مجموعة رئيسية."
        )
    else:
        lead = (
            f"{project_name}: GL expense breakdown totals {format_currency(grand_total)} "
            f"across {group_count} main group(s)."
        )

    top_bits: list[str] = []
    for group in groups[:3]:
        if not isinstance(group, dict):
            continue
        name = group.get("name") or group.get("code") or "Group"
        amount = float(group.get("total") or 0)
        top_bits.append(f"{name} ({format_currency(amount)})")

    parts = [lead]
    if top_bits:
        if language == "ar":
            parts.append(f"أبرز المجموعات: {', '.join(top_bits)}.")
        else:
            parts.append(f"Top main groups: {', '.join(top_bits)}.")
    if language == "ar":
        parts.append("راجع البطاقة للتسلسل الهرمي MG → SG → Account.")
    else:
        parts.append("See the card for the full MG → SG → Account hierarchy.")
    return " ".join(parts)


_PROFILE_LABELS = {
    "en": {
        "civil": "Civil", "electrical": "Electrical", "mechanical": "Mechanical",
        "ict": "ICT", "plumbing": "Plumbing",
        "wo_amount": "W.O Amount", "estimation": "Estimation Amount",
        "distribution": "W.O amount distribution",
        "not_set": "not set in Odoo",
        "project_manager": "Project Manager", "projects_manager": "Projects Manager",
        "branch_manager": "Branch Manager", "civil_engineer": "Civil Engineer",
        "mechanical_engineer": "Mechanical Engineer",
        "electrical_engineer": "Electrical Engineer", "ict_engineer": "ICT Engineer",
        "plumber": "Plumber", "architect": "Architect",
        "document_controller": "Document Controller",
        "start": "Start date", "end": "End date", "duration": "Duration",
        "completion": "Completion date", "days": "days",
        "status": "Status", "progress": "Overall progress",
        "client": "Client", "agreement": "Contract/Agreement",
        "wo_ref": "W.O / Ref", "code": "Project code", "city": "City",
        "operating_unit": "Operating unit", "last_updated": "Last updated",
        "created": "Created", "by": "by",
    },
    "ar": {
        "civil": "مدني", "electrical": "كهربائي", "mechanical": "ميكانيكي",
        "ict": "تقنية المعلومات", "plumbing": "سباكة",
        "wo_amount": "قيمة أمر العمل", "estimation": "قيمة التقدير",
        "distribution": "توزيع قيمة أمر العمل",
        "not_set": "غير محدد في أودو",
        "project_manager": "مدير المشروع", "projects_manager": "مدير المشاريع",
        "branch_manager": "مدير الفرع", "civil_engineer": "مهندس مدني",
        "mechanical_engineer": "مهندس ميكانيكي",
        "electrical_engineer": "مهندس كهربائي", "ict_engineer": "مهندس تقنية المعلومات",
        "plumber": "سباك", "architect": "مهندس معماري",
        "document_controller": "مراقب المستندات",
        "start": "تاريخ البدء", "end": "تاريخ الانتهاء", "duration": "المدة",
        "completion": "تاريخ الإكمال", "days": "يوم",
        "status": "الحالة", "progress": "نسبة الإنجاز",
        "client": "العميل", "agreement": "العقد/الاتفاقية",
        "wo_ref": "أمر العمل/المرجع", "code": "رمز المشروع", "city": "المدينة",
        "operating_unit": "الوحدة التشغيلية", "last_updated": "آخر تحديث",
        "created": "تاريخ الإنشاء", "by": "بواسطة",
    },
}


def _profile_amount(value: float) -> str:
    """Exact decimals — header allocations must match the Odoo UI digits."""
    return f"AED {float(value):,.2f}"


def _profile_amount_lines(amounts: dict[str, Any], labels: dict[str, str]) -> list[str]:
    lines: list[str] = []
    wo_amount = amounts.get("wo_amount")
    estimation = amounts.get("estimation_amount")
    if wo_amount is not None:
        lead = f"{labels['wo_amount']}: {_profile_amount(wo_amount)}"
        if estimation is not None and abs(float(estimation) - float(wo_amount)) >= 0.01:
            lead += f" ({labels['estimation']}: {_profile_amount(estimation)})"
        lines.append(lead + ".")

    distribution = amounts.get("distribution") or {}
    set_items = [
        (key, value) for key, value in distribution.items() if value is not None
    ]
    if set_items:
        bits = [
            f"{labels.get(key, key.title())} {_profile_amount(value)}"
            for key, value in set_items
        ]
        lines.append(f"{labels['distribution']}: " + ", ".join(bits) + ".")
    else:
        lines.append(
            f"{labels['distribution']} (Civil/Electrical/Mechanical/ICT): "
            f"{labels['not_set']}."
        )
    role_allocations = amounts.get("role_allocations") or {}
    role_bits = [
        f"{labels.get(key, key.replace('_', ' ').title())} {_profile_amount(value)}"
        for key, value in role_allocations.items()
        if value is not None
    ]
    if role_bits:
        lines.append(", ".join(role_bits) + ".")
    return lines


_ENGINEER_DISCIPLINES = ("civil", "electrical", "mechanical", "ict")


def _profile_engineer_lines(
    amounts: dict[str, Any],
    labels: dict[str, str],
    disciplines: tuple[str, ...] = _ENGINEER_DISCIPLINES,
) -> list[str]:
    """Engineer discipline amounts only — no W.O/estimation/role allocations."""
    distribution = amounts.get("distribution") or {}
    set_items = [
        (key, distribution.get(key))
        for key in disciplines
        if distribution.get(key) is not None
    ]
    if not set_items:
        asked = "/".join(labels.get(key, key.title()) for key in disciplines)
        return [f"{asked} amounts: {labels['not_set']}."]
    bits = [
        f"{labels.get(key, key.title())} {_profile_amount(value)}"
        for key, value in set_items
    ]
    return [", ".join(bits) + "."]


def _profile_team_lines(team: dict[str, Any], labels: dict[str, str]) -> list[str]:
    bits = [
        f"{labels.get(key, key.replace('_', ' ').title())}: {person['name']}"
        for key, person in team.items()
        if isinstance(person, dict) and person.get("name")
    ]
    if not bits:
        return [f"Team assignments: {labels['not_set']}."]
    return ["; ".join(bits) + "."]


def _profile_schedule_lines(schedule: dict[str, Any], labels: dict[str, str]) -> list[str]:
    bits: list[str] = []
    if schedule.get("start_date"):
        bits.append(f"{labels['start']}: {schedule['start_date']}")
    if schedule.get("end_date"):
        bits.append(f"{labels['end']}: {schedule['end_date']}")
    if schedule.get("estimated_duration_days") is not None:
        bits.append(
            f"{labels['duration']}: {schedule['estimated_duration_days']:.0f} {labels['days']}",
        )
    if schedule.get("completion_date"):
        bits.append(f"{labels['completion']}: {schedule['completion_date']}")
    if not bits:
        return [f"Schedule: {labels['not_set']}."]
    return ["; ".join(bits) + "."]


def _profile_status_lines(payload: dict[str, Any], labels: dict[str, str]) -> list[str]:
    status_section = payload.get("project_status") or {}
    progress = payload.get("progress") or {}
    bits: list[str] = []
    status_name = (status_section.get("status") or {}).get("name") if isinstance(
        status_section.get("status"), dict,
    ) else None
    state = status_name or status_section.get("state")
    if state:
        bits.append(f"{labels['status']}: {state}")
    if progress.get("overall_percent") is not None:
        line = f"{labels['progress']}: {progress['overall_percent']:.2f}%"
        if progress.get("last_update"):
            line += f" ({labels['last_updated']} {progress['last_update']})"
        bits.append(line)
    if not bits:
        return [f"{labels['status']}: {labels['not_set']}."]
    return ["; ".join(bits) + "."]


def _profile_identity_lines(payload: dict[str, Any], labels: dict[str, str]) -> list[str]:
    identity = payload.get("identity") or {}
    client_contract = payload.get("client_contract") or {}
    location = payload.get("location") or {}
    audit = payload.get("audit") or {}
    bits: list[str] = []
    if identity.get("wo_ref_no"):
        bits.append(f"{labels['wo_ref']}: {identity['wo_ref_no']}")
    if identity.get("project_code"):
        bits.append(f"{labels['code']}: {identity['project_code']}")
    client = client_contract.get("client") or {}
    if client.get("name"):
        bits.append(f"{labels['client']}: {client['name']}")
    agreement = client_contract.get("agreement") or {}
    if agreement.get("name"):
        bits.append(f"{labels['agreement']}: {agreement['name']}")
    city = location.get("city") or {}
    if city.get("name"):
        bits.append(f"{labels['city']}: {city['name']}")
    operating_unit = location.get("operating_unit") or {}
    if operating_unit.get("name"):
        bits.append(f"{labels['operating_unit']}: {operating_unit['name']}")
    updated_by = audit.get("last_updated_by") or {}
    if audit.get("last_updated_on"):
        line = f"{labels['last_updated']}: {audit['last_updated_on']}"
        if updated_by.get("name"):
            line += f" {labels['by']} {updated_by['name']}"
        bits.append(line)
    if not bits:
        return [f"Details: {labels['not_set']}."]
    return ["; ".join(bits) + "."]


def narrate_project_profile(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate the project header profile, scoped to the asked focus section."""
    del user_message
    labels = _PROFILE_LABELS["ar" if language == "ar" else "en"]
    project_name = payload.get("project_name") or "Project"
    focus = str(payload.get("focus") or "all")
    amounts = payload.get("amounts") or {}
    team = payload.get("team") or {}
    schedule = payload.get("schedule") or {}

    sections: list[str] = []
    if focus == "wo_amount":
        value = amounts.get("wo_amount")
        if value is None:
            sections.append(f"{labels['wo_amount']}: {labels['not_set']}.")
        else:
            sections.append(f"{labels['wo_amount']}: {_profile_amount(value)}.")
    elif focus == "estimation":
        value = amounts.get("estimation_amount")
        if value is None:
            sections.append(f"{labels['estimation']}: {labels['not_set']}.")
        else:
            sections.append(f"{labels['estimation']}: {_profile_amount(value)}.")
    elif focus == "amounts":
        sections += _profile_amount_lines(amounts, labels)
    elif focus == "engineers":
        sections += _profile_engineer_lines(amounts, labels)
    elif focus in _ENGINEER_DISCIPLINES:
        sections += _profile_engineer_lines(amounts, labels, disciplines=(focus,))
    elif focus == "team":
        sections += _profile_team_lines(team, labels)
    elif focus == "schedule":
        sections += _profile_schedule_lines(schedule, labels)
    elif focus == "status":
        sections += _profile_status_lines(payload, labels)
    elif focus == "identity":
        sections += _profile_identity_lines(payload, labels)
    else:
        sections += _profile_identity_lines(payload, labels)
        sections += _profile_amount_lines(amounts, labels)
        sections += _profile_team_lines(team, labels)
        sections += _profile_schedule_lines(schedule, labels)
        sections += _profile_status_lines(payload, labels)

    return f"{project_name} — " + " ".join(sections)


_RECORDS_LABELS = {
    "en": {
        "invoices": ("invoice", "invoices"),
        "client_invoices": ("client invoice", "client invoices"),
        "lpo_invoices": ("LPO invoice", "LPO invoices"),
        "purchase_orders": ("purchase order", "purchase orders"),
        "timesheets": ("timesheet entry", "timesheet entries"),
        "petty_cash": ("petty cash expense", "petty cash expenses"),
        "petty_cash_sheets": ("petty cash sheet", "petty cash sheets"),
        "staff": ("staff member", "staff members"),
        "supervisors": ("supervisor", "supervisors"),
    },
    "ar": {
        "invoices": ("فاتورة", "فواتير"),
        "client_invoices": ("فاتورة عميل", "فواتير العملاء"),
        "lpo_invoices": ("فاتورة مورد", "فواتير الموردين"),
        "purchase_orders": ("أمر شراء", "أوامر شراء"),
        "timesheets": ("سجل دوام", "سجلات دوام"),
        "petty_cash": ("مصروف نثرية", "مصاريف نثرية"),
        "petty_cash_sheets": ("كشف نثرية", "كشوف نثرية"),
        "staff": ("موظف", "موظفين"),
        "supervisors": ("مشرف", "مشرفين"),
    },
}

_UNDATED_RECORD_TYPES = frozenset({"staff", "supervisors"})


def narrate_project_records(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate a project record list: count, total, period, shown rows."""
    del user_message
    lang = "ar" if language == "ar" else "en"
    record_type = str(payload.get("record_type") or "invoices")
    singular, plural = _RECORDS_LABELS[lang].get(
        record_type, _RECORDS_LABELS[lang]["invoices"],
    )
    project_name = payload.get("project_name") or "the project"
    total = int(payload.get("total_count") or 0)
    shown = int(payload.get("returned_count") or 0)
    period = payload.get("period") or {}
    date_from = period.get("date_from")
    date_to = period.get("date_to")

    if payload.get("missing_analytic"):
        if lang == "ar":
            return (
                f"{project_name} — لا يوجد حساب تحليلي مرتبط بهذا المشروع في Odoo، "
                f"لذا لا يمكن جلب {plural}."
            )
        return (
            f"{project_name} — this project has no analytic account linked in Odoo, "
            f"so its {plural} cannot be listed."
        )

    period_bit = ""
    if record_type not in _UNDATED_RECORD_TYPES and date_from and date_to:
        if lang == "ar":
            period_bit = f" بين {date_from} و {date_to}"
            if period.get("defaulted"):
                period_bit += " (آخر ٣ أشهر افتراضياً)"
        else:
            period_bit = f" between {date_from} and {date_to}"
            if period.get("defaulted"):
                period_bit += " (last 3 months by default)"

    if total == 0:
        if lang == "ar":
            return f"{project_name} — لا توجد {plural}{period_bit}."
        return f"{project_name} — no {plural} recorded{period_bit}."

    noun = singular if total == 1 else plural
    total_amount = payload.get("total_amount")
    if record_type == "timesheets":
        amount_bit = (
            f" totalling {float(total_amount):,.1f} hours" if total_amount is not None else ""
        )
        if lang == "ar":
            amount_bit = (
                f" بمجموع {float(total_amount):,.1f} ساعة" if total_amount is not None else ""
            )
    elif total_amount is not None:
        amount_bit = f" totalling AED {float(total_amount):,.2f}"
        if lang == "ar":
            amount_bit = f" بمجموع {float(total_amount):,.2f} درهم"
    else:
        amount_bit = ""

    if lang == "ar":
        text = f"{project_name} — {total:,} {noun}{amount_bit}{period_bit}."
        if shown < total:
            text += f" يعرض أحدث {shown}."
        return text
    text = f"{project_name} — {total:,} {noun}{amount_bit}{period_bit}."
    if shown < total:
        text += f" Showing the latest {shown}."
    return text


def narrate_project_activity(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate attachments, chatter summary, progress, or audit for one project."""
    del user_message
    lang = "ar" if language == "ar" else "en"
    project_name = payload.get("project_name") or "the project"
    activity_type = str(payload.get("activity_type") or "")

    if activity_type == "chatter_summary":
        summary = str(payload.get("summary") or "").strip()
        if not summary:
            return (
                f"{project_name} — no chatter activity to summarize."
                if lang != "ar"
                else f"{project_name} — لا يوجد نشاط في سجل المشروع."
            )
        return f"{project_name} — {summary}"

    if activity_type == "attachments":
        total = int(payload.get("total_count") or 0)
        shown = int(payload.get("returned_count") or 0)
        if total == 0:
            return (
                f"{project_name} — no attachments on file."
                if lang != "ar"
                else f"{project_name} — لا توجد مرفقات."
            )
        text = f"{project_name} — {total:,} attachment{'s' if total != 1 else ''} on file."
        if shown < total:
            text += f" Showing the latest {shown}."
        return text

    data = payload.get("progress_audit") or {}
    if activity_type == "progress":
        pct = data.get("progress_percent")
        status = data.get("project_status") or data.get("state") or "unknown"
        last_upd = data.get("progress_last_update") or data.get("last_updated_on")
        delayed = data.get("delayed_weeks")
        if lang == "ar":
            bits = [f"{project_name} — التقدم"]
            if pct is not None:
                bits.append(f"{float(pct):.1f}%")
            bits.append(f"الحالة: {status}")
            if last_upd:
                bits.append(f"آخر تحديث للتقدم: {last_upd}")
            if delayed is not None:
                bits.append(f"أسابيع التأخير: {delayed}")
            return "؛ ".join(bits) + "."
        bits = [f"{project_name} — progress"]
        if pct is not None:
            bits.append(f"{float(pct):.1f}%")
        bits.append(f"status {status}")
        if last_upd:
            bits.append(f"last progress update {last_upd}")
        if delayed is not None:
            bits.append(f"{delayed} delayed weeks")
        return ", ".join(bits) + "."

    # audit
    updated_by = data.get("last_updated_by") or "not recorded"
    updated_on = data.get("last_updated_on") or "not recorded"
    created_by = data.get("created_by") or "not recorded"
    created_on = data.get("created_on") or "not recorded"
    if lang == "ar":
        return (
            f"{project_name} — أنشئ بواسطة {created_by} في {created_on}؛ "
            f"آخر تحديث بواسطة {updated_by} في {updated_on}."
        )
    return (
        f"{project_name} — created by {created_by} on {created_on}; "
        f"last updated by {updated_by} on {updated_on}."
    )


def _payload_from_expense_visualization(visualization: dict[str, Any]) -> dict[str, Any]:
    kpis = visualization.get("kpis") or {}
    wo = (kpis.get("wo_amount") or {}).get("value")
    total = (kpis.get("total_expenses") or {}).get("value")
    spend = visualization.get("spend_percent_of_wo")
    if spend is None:
        spend = (kpis.get("spend_pct") or {}).get("value")
    return {
        "project_name": visualization.get("project_name") or visualization.get("label"),
        "wo_amount": wo,
        "total_expenses": total,
        "spend_percent_of_wo": spend,
        "is_over_budget": visualization.get("is_over_budget"),
        "top_expenses": visualization.get("top_expenses") or [],
    }


def _bar_chart_rows(visualization: dict[str, Any]) -> list[dict[str, Any]]:
    data = visualization.get("data") or {}
    rows = data.get("rows") or []
    if rows:
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            label = humanize_group_label(row[0])
            try:
                value = float(row[1] or 0)
            except (TypeError, ValueError, IndexError):
                value = 0.0
            parsed.append({"label": label, "value": value})
        return parsed

    labels = data.get("labels") or []
    values = data.get("values") or []
    return [
        {"label": humanize_group_label(label), "value": float(values[index] or 0)}
        for index, label in enumerate(labels)
    ]


def _format_odoo_field_value(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2 and isinstance(value[0], int):
        return str(value[1])
    if value in (False, None, ""):
        return "—"
    return str(value)


def narrate_universal_query(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate query_odoo list results."""
    model = str(payload.get("model") or "record")
    entity = model.split(".")[-1].replace("_", " ")
    count = int(payload.get("record_count") or 0)
    records = payload.get("records") or []
    if count == 0 or not records:
        if language == "ar":
            return f"لم يتم العثور على سجلات {entity} مطابقة لهذا الطلب."
        return f"No {entity} records found matching that criteria."

    truncated = bool(payload.get("truncated"))
    suffix = "+" if truncated else ""
    if language == "ar":
        lead = f"تم العثور على {count}{suffix} سجل {entity}."
    else:
        lead = f"Found {count}{suffix} {entity} record{'s' if count != 1 else ''}."

    sample_fields = [
        key
        for key in records[0].keys()
        if key not in {"id", "__last_update", "display_name"}
    ][:4]
    lines: list[str] = []
    for record in records[:10]:
        if not isinstance(record, dict):
            continue
        label = _format_odoo_field_value(record.get("name"))
        if label == "—" and sample_fields:
            label = " · ".join(
                part
                for part in (_format_odoo_field_value(record.get(field)) for field in sample_fields)
                if part != "—"
            )
        if label == "—":
            label = str(record.get("id", "record"))
        lines.append(f"- {label}")

    body = "\n".join(lines)
    if count > 10:
        more = count - 10
        body += f"\n…and {more} more." if language != "ar" else f"\n…و{more} أخرى."
    return f"{lead}\n{body}"


def narrate_universal_aggregate(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate aggregate_odoo grouped results."""
    groups = payload.get("groups") or []
    model = str(payload.get("model") or "record")
    entity = model.split(".")[-1].replace("_", " ")
    if not groups:
        return f"No grouped {entity} results found for that criteria."

    if model == "hr.payslip.cost.allocation":
        if any(isinstance(g, dict) and g.get("month") for g in groups):
            lines: list[str] = []
            for group in groups[:12]:
                if not isinstance(group, dict):
                    continue
                amt = float(group.get("amount") or 0)
                month = group.get("month") or "?"
                year = group.get("year") or "?"
                lines.append(f"- {month}/{year}: {format_currency(amt)}")
            if lines:
                return "Labor cost trend:\n" + "\n".join(lines)

        if any(isinstance(g, dict) and g.get("employee_id") for g in groups):
            lines = []
            for group in groups[:20]:
                if not isinstance(group, dict):
                    continue
                emp = group.get("employee_id")
                label = str(emp[1]) if isinstance(emp, (list, tuple)) and len(emp) >= 2 else str(emp)
                amt = float(group.get("amount") or 0)
                lines.append(f"- {label}: {format_currency(amt)}")
            if lines:
                lead = "Labor cost by employee:" if language != "ar" else "تكلفة العمالة حسب الموظف:"
                return lead + "\n" + "\n".join(lines)

        if len(groups) > 1 and any(
            isinstance(g, dict) and g.get("project_id") for g in groups
        ):
            lines = []
            for group in groups[:15]:
                if not isinstance(group, dict):
                    continue
                proj = group.get("project_id")
                label = str(proj[1]) if isinstance(proj, (list, tuple)) and len(proj) >= 2 else str(proj)
                amt = float(group.get("amount") or 0)
                lines.append(f"- {label}: {format_currency(amt)}")
            if lines:
                lead = "Labor cost by project:" if language != "ar" else "تكلفة العمالة حسب المشروع:"
                return lead + "\n" + "\n".join(lines)

        total_amount = 0.0
        project_label = "the project"
        for group in groups[:15]:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                if key == "amount" and isinstance(value, (int, float)):
                    total_amount += float(value)
                elif key == "project_id" and isinstance(value, (list, tuple)) and len(value) >= 2:
                    project_label = str(value[1])
        if language == "ar":
            return f"إجمالي تكلفة العمالة لـ {project_label}: {format_currency(total_amount)}."
        return f"Labor cost for {project_label} is {format_currency(total_amount)}."

    if model == "hr.payslip":
        parts: list[str] = []
        for group in groups[:10]:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                if key.startswith("__") or not isinstance(value, (int, float)):
                    continue
                if any(token in key for token in ("salary", "fine", "over_time", "deduction", "amount")):
                    label = key.replace("_", " ").replace(":sum", "").replace(":avg", "")
                    parts.append(f"{label}: {format_currency(float(value))}")
                if key.endswith("_count") or key.endswith(":count"):
                    parts.append(f"count: {int(float(value)):,}")
        if parts:
            return "Payroll aggregate — " + "; ".join(parts[:8]) + "."

    if model == "hr.payslip.worked_days":
        total_hours = 0.0
        total_amount = 0.0
        for group in groups:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                if isinstance(value, (int, float)) and "hour" in key:
                    total_hours += float(value)
                if key == "amount" or key.endswith("amount"):
                    if isinstance(value, (int, float)):
                        total_amount += float(value)
        if total_hours > 0:
            return f"Total worked-day hours: {total_hours:,.1f}."
        if total_amount > 0:
            return f"Worked-day amount total: {format_currency(total_amount)}."

    if model == "employee.requests":
        total_count = 0
        dept_lines: list[str] = []
        for group in groups[:15]:
            if not isinstance(group, dict):
                continue
            count_value = group.get("__count")
            if count_value is None:
                for key, value in group.items():
                    if key.endswith("_count") or key.endswith(":count"):
                        count_value = value
                        break
            try:
                count_int = int(float(count_value or 0))
            except (TypeError, ValueError):
                count_int = 0
            total_count += count_int
            label = "—"
            for key, value in group.items():
                if key.startswith("__") or key.endswith("_count") or key.endswith(":count"):
                    continue
                label = humanize_group_label(value)
                if label != "Unassigned":
                    break
            if len(groups) > 1:
                dept_lines.append(f"- {label}: {count_int:,}")
        blob = (user_message or "").lower()
        event = "terminations"
        if "resign" in blob:
            event = "resignations"
        elif "clearance" in blob:
            event = "clearance"
        elif "leave" in blob:
            event = "leave requests"
        if len(groups) <= 1:
            return f"{total_count:,} {event} in the selected period."
        lead = f"{total_count:,} {event} in the selected period by department:"
        return lead + "\n" + "\n".join(dept_lines)

    lines: list[str] = []
    total_count = 0
    for group in groups[:15]:
        if not isinstance(group, dict):
            continue
        label = "—"
        for key, value in group.items():
            if key.startswith("__") or key.endswith("_count") or key.endswith(":count"):
                continue
            label = humanize_group_label(value)
            if label != "Unassigned":
                break
        count_value = group.get("__count")
        if count_value is None:
            for key, value in group.items():
                if key.endswith("_count") or key.endswith(":count"):
                    count_value = value
                    break
        try:
            count_int = int(float(count_value or 0))
        except (TypeError, ValueError):
            count_int = 0
        total_count += count_int
        count_text = f"{count_int:,}"
        lines.append(f"- {label}: {count_text}")

    if "employee" in entity and total_count > 0:
        lead = f"Elrace has {total_count:,} active employees across {len(groups)} department{'s' if len(groups) != 1 else ''}."
    else:
        lead = f"Grouped {entity} results ({len(groups)} group{'s' if len(groups) != 1 else ''}, total {total_count:,}):"
    return f"{lead}\n" + "\n".join(lines)


def narrate_financial_report(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate company financial report KPIs."""
    kpis = payload.get("kpis") or {}
    if not isinstance(kpis, dict) or not kpis:
        return ""

    income = float(kpis.get("total_income") or 0)
    expense = float(kpis.get("total_expense") or 0)
    profit = float(kpis.get("net_profit") or kpis.get("total_cost") or (income - expense))
    date_from = payload.get("date_from") or ""
    date_to = payload.get("date_to") or ""
    period = f"{date_from} to {date_to}".strip(" to")

    if language == "ar":
        return (
            f"ملخص الأرباح والخسائر ({period}): "
            f"الإيرادات {format_currency(income)}، "
            f"المصروفات {format_currency(expense)}، "
            f"صافي الربح {format_currency(profit)}."
        )
    return (
        f"P&L summary ({period}): revenue {format_currency(income)}, "
        f"expenses {format_currency(expense)}, net profit {format_currency(profit)}."
    )


def narrate_project_expense_comparison(
    payload: dict[str, Any],
    *,
    user_message: str = "",
    language: str = "en",
) -> str:
    """Narrate compare_project_expenses side-by-side results."""
    projects = payload.get("projects") or []
    if len(projects) < 2:
        return ""
    lines: list[str] = []
    for project in projects[:10]:
        if not isinstance(project, dict):
            continue
        name = project.get("project_name") or f"Project {project.get('project_id')}"
        total = float(project.get("total_expenses") or 0)
        lines.append(f"- {name}: {format_currency(total)}")
    lead = "Project expense comparison:"
    return f"{lead}\n" + "\n".join(lines)


_ORCHESTRATION_META_RE = re.compile(
    r"Completed\s+\d+\s+orchestrated\s+step",
    re.IGNORECASE,
)


def is_orchestration_meta_text(text: str) -> bool:
    """True when synthesizer leaked pipeline metadata into user text."""
    return bool(_ORCHESTRATION_META_RE.search(text or ""))


def generate_narrative(
    user_message: str,
    visualization: dict[str, Any] | None,
    tool_results: list[Any],
    language: str = "en",
) -> str:
    for result in reversed(tool_results):
        if not isinstance(result, dict) or result.get("error"):
            continue
        source = str(result.get("_source") or "")
        if source == "universal_odoo_query" and result.get("status") == "success":
            return narrate_universal_query(result, user_message=user_message, language=language)
        if source == "universal_odoo_aggregate" and result.get("status") == "success":
            return narrate_universal_aggregate(result, user_message=user_message, language=language)
        if result.get("kpis") and result.get("report_lines") is not None:
            text = narrate_financial_report(result, user_message=user_message, language=language)
            if text:
                return text
        if source == "compare_project_expenses" and result.get("status") == "success":
            text = narrate_project_expense_comparison(result, user_message=user_message, language=language)
            if text:
                return text

    if not visualization:
        for result in reversed(tool_results):
            if not isinstance(result, dict) or result.get("error"):
                continue
            if result.get("quality_warning"):
                return str(result["quality_warning"])
            if result.get("groups") and not result.get("groups"):
                return (
                    "No matching records were found for that period. "
                    "Try a wider date range or confirm the filters."
                )
        return ""

    visual_type = visualization.get("visual_type")
    if visual_type == "PROJECT_EXPENSE_SUMMARY":
        for result in reversed(tool_results):
            if isinstance(result, dict) and result.get("_source") in {
                "project_expense_summary",
                "project_expense_summary_mobile",
                "project_expense_dashboard",
            }:
                return narrate_project_expense_summary(
                    result,
                    user_message=user_message,
                    language=language,
                )
        return narrate_project_expense_summary(
            _payload_from_expense_visualization(visualization),
            user_message=user_message,
            language=language,
        )

    if visual_type == "PROJECT_EXPENSE_BREAKDOWN":
        for result in reversed(tool_results):
            if isinstance(result, dict) and result.get("_source") == "project_expense_breakdown_mobile":
                return narrate_project_expense_breakdown(
                    result,
                    user_message=user_message,
                    language=language,
                )
        return narrate_project_expense_breakdown(
            {
                "project_name": visualization.get("project_name"),
                "currency": visualization.get("currency"),
                "grand_total": visualization.get("grand_total"),
                "group_count": visualization.get("group_count"),
                "groups": visualization.get("groups") or [],
            },
            user_message=user_message,
            language=language,
        )

    if visual_type == "BAR_CHART":
        rows = _bar_chart_rows(visualization)
        rows = [row for row in rows if row["value"] > 0]
        if not rows:
            return (
                "I did not find any positive values for that comparison. "
                "The posted records for this period may be empty or filtered out."
            )
        rows.sort(key=lambda item: item["value"], reverse=True)
        total = sum(row["value"] for row in rows)
        leader = rows[0]
        leader_share = (leader["value"] / total) * 100 if total else 0
        if language == "ar":
            return (
                f"يتصدر {leader['label']} بقيمة {format_currency(leader['value'])} "
                f"({format_percentage(leader_share)} من الإجمالي). "
                f"إجمالي النتائج المعروضة {format_currency(total)}."
            )
        return (
            f"{leader['label']} leads with {format_currency(leader['value'])} "
            f"({format_percentage(leader_share)} of the total). "
            f"The visible results total {format_currency(total)}."
        )

    if visual_type == "DATA_TABLE":
        rows = (visualization.get("data") or {}).get("rows") or []
        if rows:
            return (
                f"Here are {len(rows)} rows for your request. "
                "Use the table to review the ranked or grouped results."
            )

    if visual_type == "KPI_CARD":
        value = visualization.get("value")
        label = visualization.get("label") or "Result"
        unit = visualization.get("unit") or ""
        if unit.upper() == "AED":
            return f"{label}: {format_currency(value)}."
        return f"{label}: {format_number(value)}." if value is not None else f"{label} is ready."

    if visual_type == "FINANCIAL_REPORT":
        for result in reversed(tool_results):
            if isinstance(result, dict) and isinstance(result.get("kpis"), dict):
                text = narrate_financial_report(result, user_message=user_message, language=language)
                if text:
                    return text
        kpis = visualization.get("kpis") or {}
        if isinstance(kpis, dict) and kpis:
            return narrate_financial_report(
                {"kpis": kpis, "date_from": visualization.get("date_from"), "date_to": visualization.get("date_to")},
                user_message=user_message,
                language=language,
            )

    if visual_type == "PROJECT_EXPENSE_COMPARISON":
        for result in reversed(tool_results):
            if isinstance(result, dict) and result.get("_source") == "compare_project_expenses":
                text = narrate_project_expense_comparison(result, user_message=user_message, language=language)
                if text:
                    return text

    if visual_type == "GROUPED_TABLE":
        groups = (visualization.get("data") or {}).get("groups") or []
        if groups:
            return (
                f"The breakdown includes {len(groups)} top-level groups. "
                "Expand a group to review the nested detail."
            )

    return ""


def format_number(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)
