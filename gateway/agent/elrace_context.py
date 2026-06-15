"""Elrace business context injected into agent system prompts."""

from __future__ import annotations

from gateway.core.business_context import BusinessContext

_business = BusinessContext()

ELRACE_CONTEXT = f"""
ELRACE BUSINESS CONTEXT:
{_business.summary().strip()}

Key patterns:
- "maintenance" usually means project.project with maintenance category
- Default currency: AED; fiscal year Jan–Dec
- Company-wide P&L requires all journals + operating units (handled by financial tools)
- Income accounts may store negative credit balances — use abs() for display
- project_name_arabic field has unreliable data — prefer English names + WO ref
- When user mentions a person by first name only, search hr.employee before asking again
- Fleet queries: use search_fleet_vehicles with employee_name or employee_file_id
"""
