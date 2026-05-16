from __future__ import annotations

import logging
from typing import Any

from gateway.accounting_sql.connection import accounting_cursor, accounting_sql_enabled
from gateway.accounting_sql.dates import resolve_as_of_date, resolve_date_range
from gateway.accounting_sql.executor import execute_recipe_sql
from gateway.accounting_sql.odoo_fallback import execute_report_via_odoo
from gateway.accounting_sql.post_process import post_process_report
from gateway.accounting_sql.recipes import REPORT_RECIPES, SUPPORTED_REPORT_TYPES

logger = logging.getLogger(__name__)


def _merge_params(tool_input: dict[str, Any]) -> dict[str, Any]:
    report_type = tool_input.get("report_type")
    if report_type not in REPORT_RECIPES:
        return dict(tool_input)

    recipe = REPORT_RECIPES[report_type]
    merged = {**recipe, **tool_input}
    return merged


def _validate_request(params: dict[str, Any]) -> dict[str, Any] | None:
    report_type = params.get("report_type")
    if not report_type:
        return {
            "error": "missing_report_type",
            "message": "report_type is required.",
            "supported_report_types": list(SUPPORTED_REPORT_TYPES),
        }

    if report_type not in REPORT_RECIPES:
        return {
            "error": "unsupported_report_type",
            "message": f"Unsupported report_type '{report_type}'.",
            "supported_report_types": list(SUPPORTED_REPORT_TYPES),
        }

    recipe = REPORT_RECIPES[report_type]
    if not recipe.get("implemented"):
        return {
            "error": "report_not_implemented_yet",
            "message": (
                f"Report '{report_type}' is planned but not implemented in this phase."
            ),
            "supported_report_types": [
                key for key, value in REPORT_RECIPES.items() if value.get("implemented")
            ],
        }

    company_id = int(params.get("company_id", 1))
    params["company_id"] = company_id
    if params.get("account_ids") and isinstance(params["account_ids"], list):
        params["account_ids"] = [int(value) for value in params["account_ids"]]

    if recipe.get("requires_date_range"):
        date_from, date_to = resolve_date_range(params.get("date_from"), params.get("date_to"))
        params["date_from"] = date_from
        params["date_to"] = date_to

    if recipe.get("requires_as_of_date"):
        params["as_of_date"] = resolve_as_of_date(params.get("as_of_date"), params.get("date_to"))
        if not params.get("date_from"):
            params["date_from"] = "1900-01-01"
        params["date_to"] = params["as_of_date"]

    return None


def execute_query_accounting(
    tool_input: dict[str, Any],
    adapter: Any | None = None,
) -> dict[str, Any]:
    params = _merge_params(tool_input or {})
    validation_error = _validate_request(params)
    if validation_error:
        return validation_error

    report_type = params["report_type"]
    logger.info(
        "[query_accounting] report_type=%s date_from=%s date_to=%s company_id=%s",
        report_type,
        params.get("date_from"),
        params.get("date_to"),
        params.get("company_id"),
    )

    if accounting_sql_enabled():
        try:
            with accounting_cursor() as cursor:
                rows = execute_recipe_sql(cursor, report_type, params)
            return post_process_report(report_type, rows, params)
        except NotImplementedError:
            logger.info("[query_accounting] SQL not implemented for %s, trying Odoo", report_type)
        except Exception as exc:
            logger.warning("[query_accounting] SQL failed for %s: %s", report_type, exc)

    if adapter is not None:
        try:
            return execute_report_via_odoo(adapter, params)
        except Exception as exc:
            logger.exception("[query_accounting] Odoo fallback failed for %s", report_type)
            return {
                "error": "query_accounting_failed",
                "message": str(exc),
                "report_type": report_type,
                "user_message": "The accounting report could not be loaded from Odoo.",
                "recovery": {
                    "switch_strategy": True,
                    "fallback_tool": "get_financial_report",
                },
            }

    return {
        "error": "accounting_sql_unavailable",
        "message": "ODOO_POSTGRES_DSN is not configured and no Odoo adapter was provided.",
        "user_message": (
            "Configure ODOO_POSTGRES_DSN for direct SQL, or call query_accounting via the gateway "
            "so Odoo XML-RPC can be used."
        ),
    }
