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
    if focus == "amounts":
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


def generate_narrative(
    user_message: str,
    visualization: dict[str, Any] | None,
    tool_results: list[Any],
    language: str = "en",
) -> str:
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
