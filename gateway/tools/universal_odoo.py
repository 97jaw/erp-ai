"""Universal Odoo access tools — demo-ready version.

Gives Claude read-only access to ANY Odoo model so it can answer
HR, payroll, inventory, purchase, sales, fleet, FSM questions —
not just projects and financials.

Three tools:
  - introspect_odoo_schema : discover models + fields
  - query_odoo             : read records
  - aggregate_odoo         : sum/count/avg with grouping

Five safety layers:
  1. Forbidden models (credentials, system)
  2. Permission-based access (super admin vs roles)
  3. Read-only (no create/write/unlink)
  4. Query limits (max 500, must specify fields)
  5. PII redaction (wages/bank for non-super-admin)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# SAFETY CONSTANTS
# ─────────────────────────────────────────────────────────────

FORBIDDEN_MODELS = {
    "res.users",
    "res.users.log",
    "res.users.apikeys",
    "res.users.apikeys.description",
    "ir.config_parameter",
    "ir.mail_server",
    "fetchmail.server",
    "auth.totp.device",
    "ir.logging",
}

SENSITIVE_MODELS = {
    "hr.payslip",
    "hr.payslip.line",
    "hr.payslip.run",
    "hr.contract",
    "account.payment",
    "res.bank",
    "res.partner.bank",
}

# Field-level redaction for non-super-admin (level < 100)
REDACT_FIELDS = {
    "hr.payslip": ["net_wage", "gross_wage", "amount", "total", "basic"],
    "hr.contract": ["wage", "salary"],
    "res.partner.bank": ["acc_number"],
}


# ─────────────────────────────────────────────────────────────
# PERMISSION HELPERS
# ─────────────────────────────────────────────────────────────

def _user_level(context: Any) -> int:
    """Extract user level from context. Defaults to super admin for demo."""
    try:
        return int(getattr(context.user, "level", 100))
    except Exception:
        return 100  # Demo default: treat as super admin


def _can_see_model(model: str, context: Any) -> bool:
    """Permission check for model access."""
    if model in FORBIDDEN_MODELS:
        return False
    level = _user_level(context)
    if level >= 100:  # Super admin
        return True
    if level >= 70:  # Top management — no sensitive
        return model not in SENSITIVE_MODELS
    # Lower roles: allow common read models, block sensitive
    return model not in SENSITIVE_MODELS


def build_universal_context(*, user_message: str = "", user: Any = None) -> Any:
    """Build a ContextStack for universal tool calls (permissions + redaction)."""
    from gateway.tools.search_entities import minimal_search_context

    ctx = minimal_search_context(user_message=user_message)
    if user is not None:
        ctx.user.user_id = int(user.id)
        ctx.user.name = str(getattr(user, "name", "User"))
        ctx.user.file_id = str(getattr(user, "file_id", "") or "")
        ctx.user.level = 100 if getattr(user, "is_super_admin", False) else 70
        perms = set(getattr(user, "permissions", ()) or ())
        if getattr(user, "is_super_admin", False):
            perms.add("data.all_projects")
        ctx.user.permissions = perms
    return ctx


def _adapter_fields_get(adapter: Any, model: str) -> dict[str, Any]:
    if hasattr(adapter, "_execute"):
        return adapter._execute(
            model,
            "fields_get",
            [],
            {"attributes": ["string", "type", "relation", "help", "selection"]},
        )
    return adapter.execute_kw(
        model,
        "fields_get",
        [],
        {"attributes": ["string", "type", "relation", "help", "selection"]},
    )


def _redact(model: str, records: list[dict], context: Any) -> list[dict]:
    """Redact sensitive fields for non-super-admin."""
    if _user_level(context) >= 100:
        return records
    fields = REDACT_FIELDS.get(model, [])
    if not fields:
        return records
    for r in records:
        for f in fields:
            if f in r:
                r[f] = "***restricted***"
    return records


# ─────────────────────────────────────────────────────────────
# TOOL 1: introspect_odoo_schema
# ─────────────────────────────────────────────────────────────

async def execute_introspect_odoo_schema(
    adapter: Any,
    tool_input: dict,
    context: Any,
) -> dict:
    """Discover models or get field details for one model."""
    search = (tool_input.get("search") or "").strip().lower()
    model = (tool_input.get("model") or "").strip()

    if model:
        return await _describe_model(adapter, model, context)
    return await _list_models(adapter, search, context)


async def _list_models(adapter: Any, search: str, context: Any) -> dict:
    domain = []
    if search:
        domain = ["|", "|",
                  ["model", "ilike", search],
                  ["name", "ilike", search],
                  ["info", "ilike", search]]
    try:
        models = await asyncio.to_thread(
            adapter.safe_search_read,
            "ir.model", domain,
            ["model", "name", "info", "transient"],
            limit=40,
        )
    except Exception as e:
        return {"status": "error", "message": f"Schema lookup failed: {e}"}

    out = []
    for m in models:
        if m.get("transient"):
            continue
        if not _can_see_model(m["model"], context):
            continue
        out.append({
            "model": m["model"],
            "label": m.get("name"),
            "description": (m.get("info") or "")[:160],
        })
    return {
        "status": "success",
        "search": search,
        "model_count": len(out),
        "models": out,
        "_note": "Call again with 'model' to get field details.",
    }


async def _describe_model(adapter: Any, model: str, context: Any) -> dict:
    if not _can_see_model(model, context):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": f"No access to '{model}'.",
        }
    try:
        fields = await asyncio.to_thread(_adapter_fields_get, adapter, model)
    except Exception as e:
        return {"status": "error", "message": f"Model '{model}' not found: {e}"}

    useful = {}
    for fname, finfo in fields.items():
        if fname.startswith("_"):
            continue
        entry = {
            "label": finfo.get("string", fname),
            "type": finfo.get("type"),
        }
        if finfo.get("relation"):
            entry["relation"] = finfo["relation"]
        if finfo.get("help"):
            entry["help"] = (finfo["help"] or "")[:200]
        if finfo.get("selection"):
            entry["values"] = finfo["selection"]
        useful[fname] = entry

    return {
        "status": "success",
        "model": model,
        "field_count": len(useful),
        "fields": useful,
        "is_sensitive": model in SENSITIVE_MODELS,
    }


# ─────────────────────────────────────────────────────────────
# TOOL 2: query_odoo
# ─────────────────────────────────────────────────────────────

async def execute_query_odoo(
    adapter: Any,
    tool_input: dict,
    context: Any,
) -> dict:
    """Read records from any Odoo model. Read-only."""
    model = (tool_input.get("model") or "").strip()
    domain = tool_input.get("domain") or []
    fields = tool_input.get("fields") or []
    limit = min(int(tool_input.get("limit") or 50), 500)
    order = tool_input.get("order")

    if not model:
        return {"status": "error", "message": "model is required"}

    if model in FORBIDDEN_MODELS:
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"'{model}' is restricted (system/credentials).",
        }

    if not _can_see_model(model, context):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": f"Your role cannot read '{model}'.",
        }

    if not fields:
        return {
            "status": "error",
            "error_code": "fields_required",
            "message": "Specify fields. Use introspect_odoo_schema if unsure.",
        }

    try:
        kwargs: dict[str, Any] = {"limit": limit}
        if order:
            kwargs["order"] = order
        records = await asyncio.to_thread(
            adapter.safe_search_read, model, domain, fields, **kwargs,
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "query_failed",
            "message": str(e),
            "model": model,
            "domain": domain,
        }

    if model in SENSITIVE_MODELS:
        records = _redact(model, records, context)

    logger.info("[query_odoo] model=%s domain=%s rows=%d",
                model, domain, len(records))

    return {
        "status": "success",
        "model": model,
        "record_count": len(records),
        "records": records,
        "truncated": len(records) == limit,
        "_source": "universal_odoo_query",
    }


# ─────────────────────────────────────────────────────────────
# TOOL 3: aggregate_odoo
# ─────────────────────────────────────────────────────────────

async def execute_aggregate_odoo(
    adapter: Any,
    tool_input: dict,
    context: Any,
) -> dict:
    """Aggregate (sum/count/avg) grouped by fields, via read_group."""
    model = (tool_input.get("model") or "").strip()
    domain = tool_input.get("domain") or []
    group_by = tool_input.get("group_by") or []
    aggregates = tool_input.get("aggregates") or []
    limit = min(int(tool_input.get("limit") or 50), 200)

    if not model:
        return {"status": "error", "message": "model is required"}

    if model in FORBIDDEN_MODELS:
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"'{model}' is restricted.",
        }

    if not _can_see_model(model, context):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": f"Your role cannot read '{model}'.",
        }

    if not aggregates or not group_by:
        return {
            "status": "error",
            "message": "Both group_by and aggregates are required.",
        }

    try:
        results = await asyncio.to_thread(
            adapter.read_group,
            model,
            domain,
            aggregates,
            group_by,
            limit=limit,
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "aggregation_failed",
            "message": str(e),
        }

    # Redact sensitive aggregates for non-super-admin
    if model in SENSITIVE_MODELS and _user_level(context) < 100:
        for r in results:
            for key in list(r.keys()):
                if any(s in key.lower() for s in ("wage", "salary", "amount", "total")):
                    r[key] = "***restricted***"

    logger.info("[aggregate_odoo] model=%s group_by=%s rows=%d",
                model, group_by, len(results))

    return {
        "status": "success",
        "model": model,
        "group_by": group_by,
        "aggregates": aggregates,
        "group_count": len(results),
        "groups": results,
        "_source": "universal_odoo_aggregate",
    }


# ─────────────────────────────────────────────────────────────
# TOOL DEFINITIONS (for the TOOLS array in main.py)
# ─────────────────────────────────────────────────────────────

UNIVERSAL_ODOO_TOOL_DEFINITIONS = [
    {
        "name": "introspect_odoo_schema",
        "description": (
            "Discover Odoo models and their fields. Use when you need to "
            "query an area outside projects/financials (HR, payroll, "
            "inventory, sales, purchase, fleet, FSM) and need to know the "
            "model name or fields. Pass 'search' to find models, or 'model' "
            "to get field details for one model."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {"type": "string",
                           "description": "Keyword to find models, e.g. 'employee', 'stock'"},
                "model": {"type": "string",
                          "description": "Exact model name for field details, e.g. 'hr.employee'"},
            },
        },
    },
    {
        "name": "query_odoo",
        "description": (
            "Read records from ANY Odoo model (read-only). Use for HR "
            "(hr.employee, hr.department), payroll (hr.payslip), inventory "
            "(stock.quant, product.product), purchase (purchase.order), sales "
            "(sale.contracted.order), fleet (fleet.vehicle), FSM (fsm.order), "
            "and custom Elrace models.\n\n"
            "DO NOT use for: P&L/balance sheet (get_financial_report), project "
            "expenses (get_project_expense_summary), partner ageing "
            "(get_partner_ageing). Those have specialized tools.\n\n"
            "If unsure of model/fields, call introspect_odoo_schema first. "
            "Always specify the fields you need."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "domain": {"type": "array",
                           "description": "Odoo domain, e.g. [['active','=',true]]",
                           "default": []},
                "fields": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 50},
                "order": {"type": "string"},
            },
            "required": ["model", "fields"],
        },
    },
    {
        "name": "aggregate_odoo",
        "description": (
            "Aggregate Odoo records (sum/count/avg/max/min) grouped by fields. "
            "Use for totals like 'total payroll for May', 'employee count per "
            "department', 'PO total by supplier'. aggregates format: "
            "['field:operation'] e.g. ['net_wage:sum', 'id:count']."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "domain": {"type": "array", "default": []},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "aggregates": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["model", "group_by", "aggregates"],
        },
    },
]


# Dispatch map for execute_tool wiring in main.py
UNIVERSAL_ODOO_EXECUTORS = {
    "introspect_odoo_schema": execute_introspect_odoo_schema,
    "query_odoo": execute_query_odoo,
    "aggregate_odoo": execute_aggregate_odoo,
}
