from __future__ import annotations

import logging
from typing import Any

from gateway.accounting_sql.schema import (
    AccountingSchema,
    account_type_filter_sql,
    balance_sheet_group_expr,
    balance_sheet_type_filter_sql,
    expense_type_filter_sql,
    load_schema,
    pandl_type_filter_sql,
    sql_internal_group_expr,
)

logger = logging.getLogger(__name__)


def execute_trial_balance_sql(
    cursor: Any,
    schema: AccountingSchema,
    *,
    company_id: int,
    date_from: str,
    date_to: str,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    account_filter = account_type_filter_sql(schema)
    sql = f"""
        SELECT
            aa.id AS account_id,
            aa.code AS account_code,
            aa.name AS account_name,
            COALESCE(SUM(aml.debit), 0) AS debit_sum,
            COALESCE(SUM(aml.credit), 0) AS credit_sum,
            COALESCE(SUM(aml.debit), 0) - COALESCE(SUM(aml.credit), 0) AS balance_sum
        FROM account_move_line aml
        INNER JOIN account_move am ON aml.move_id = am.id
        INNER JOIN account_account aa ON aml.account_id = aa.id
        LEFT JOIN account_account_type aat ON aa.user_type_id = aat.id
        WHERE am.state = 'posted'
          AND aml.company_id = %s
          AND aml.date >= %s
          AND aml.date <= %s
          AND {account_filter}
        GROUP BY aa.id, aa.code, aa.name
        HAVING COALESCE(SUM(aml.debit), 0) <> 0
            OR COALESCE(SUM(aml.credit), 0) <> 0
        ORDER BY aa.code ASC
        LIMIT %s
    """
    cursor.execute(sql, (company_id, date_from, date_to, limit))
    return [dict(row) for row in cursor.fetchall()]


def execute_pandl_sql(
    cursor: Any,
    schema: AccountingSchema,
    *,
    company_id: int,
    date_from: str,
    date_to: str,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    account_filter = account_type_filter_sql(schema)
    pandl_filter = pandl_type_filter_sql(schema)
    group_expr = sql_internal_group_expr(schema)
    sql = f"""
        SELECT
            {group_expr} AS internal_group,
            aa.id AS account_id,
            aa.code AS account_code,
            aa.name AS account_name,
            COALESCE(SUM(aml.debit), 0) AS debit_sum,
            COALESCE(SUM(aml.credit), 0) AS credit_sum,
            COALESCE(SUM(aml.credit), 0) - COALESCE(SUM(aml.debit), 0) AS balance_sum
        FROM account_move_line aml
        INNER JOIN account_move am ON aml.move_id = am.id
        INNER JOIN account_account aa ON aml.account_id = aa.id
        LEFT JOIN account_account_type aat ON aa.user_type_id = aat.id
        WHERE am.state = 'posted'
          AND aml.company_id = %s
          AND aml.date >= %s
          AND aml.date <= %s
          AND {account_filter}
          AND {pandl_filter}
        GROUP BY {group_expr}, aa.id, aa.code, aa.name
        HAVING COALESCE(SUM(aml.debit), 0) <> 0
            OR COALESCE(SUM(aml.credit), 0) <> 0
        ORDER BY {group_expr}, aa.code ASC
        LIMIT %s
    """
    cursor.execute(sql, (company_id, date_from, date_to, limit))
    return [dict(row) for row in cursor.fetchall()]


def execute_recipe_sql(
    cursor: Any,
    report_type: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    schema = load_schema(cursor)
    if report_type == "trial_balance":
        return execute_trial_balance_sql(
            cursor,
            schema,
            company_id=int(params.get("company_id", 1)),
            date_from=params["date_from"],
            date_to=params["date_to"],
            limit=int(params.get("limit", 5000)),
        )
    if report_type == "pandl":
        return execute_pandl_sql(
            cursor,
            schema,
            company_id=int(params.get("company_id", 1)),
            date_from=params["date_from"],
            date_to=params["date_to"],
            limit=int(params.get("limit", 5000)),
        )
    if report_type == "balance_sheet":
        return execute_balance_sheet_sql(
            cursor,
            schema,
            company_id=int(params.get("company_id", 1)),
            as_of_date=params["date_to"],
            limit=int(params.get("limit", 5000)),
        )
    if report_type == "general_ledger":
        return execute_general_ledger_sql(
            cursor,
            schema,
            company_id=int(params.get("company_id", 1)),
            date_from=params["date_from"],
            date_to=params["date_to"],
            account_ids=params.get("account_ids"),
            limit=int(params.get("limit", 10000)),
        )
    if report_type == "cost_analysis":
        return execute_cost_analysis_sql(
            cursor,
            schema,
            company_id=int(params.get("company_id", 1)),
            date_from=params["date_from"],
            date_to=params["date_to"],
            analytic_ids=params.get("analytic_ids"),
            operating_unit_ids=params.get("operating_unit_ids"),
            limit=int(params.get("limit", 5000)),
        )
    raise NotImplementedError(f"SQL recipe not implemented yet: {report_type}")


def execute_cost_analysis_sql(
    cursor: Any,
    schema: AccountingSchema,
    *,
    company_id: int,
    date_from: str,
    date_to: str,
    analytic_ids: list[int] | None = None,
    operating_unit_ids: list[int] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    account_filter = account_type_filter_sql(schema)
    expense_filter = expense_type_filter_sql(schema)
    extra_clauses = ""
    params: list[Any] = [company_id, date_from, date_to]
    if analytic_ids:
        extra_clauses += " AND aml.analytic_account_id = ANY(%s)"
        params.append(analytic_ids)
    if operating_unit_ids:
        extra_clauses += " AND aml.operating_unit_id = ANY(%s)"
        params.append(operating_unit_ids)
    params.append(limit)

    sql = f"""
        SELECT
            aml.analytic_account_id AS analytic_account_id,
            COALESCE(aaa.name, 'Unallocated') AS analytic_account_name,
            aa.id AS account_id,
            aa.code AS account_code,
            aa.name AS account_name,
            COALESCE(SUM(aml.debit), 0) AS debit_sum,
            COALESCE(SUM(aml.credit), 0) AS credit_sum,
            COALESCE(SUM(aml.debit), 0) - COALESCE(SUM(aml.credit), 0) AS cost_amount
        FROM account_move_line aml
        INNER JOIN account_move am ON aml.move_id = am.id
        INNER JOIN account_account aa ON aml.account_id = aa.id
        LEFT JOIN account_account_type aat ON aa.user_type_id = aat.id
        LEFT JOIN account_analytic_account aaa ON aml.analytic_account_id = aaa.id
        WHERE am.state = 'posted'
          AND aml.company_id = %s
          AND aml.date >= %s
          AND aml.date <= %s
          AND {account_filter}
          AND {expense_filter}
          {extra_clauses}
        GROUP BY aml.analytic_account_id, aaa.name, aa.id, aa.code, aa.name
        HAVING COALESCE(SUM(aml.debit), 0) <> 0
            OR COALESCE(SUM(aml.credit), 0) <> 0
        ORDER BY cost_amount DESC
        LIMIT %s
    """
    cursor.execute(sql, tuple(params))
    return [dict(row) for row in cursor.fetchall()]


def execute_balance_sheet_sql(
    cursor: Any,
    schema: AccountingSchema,
    *,
    company_id: int,
    as_of_date: str,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    account_filter = account_type_filter_sql(schema)
    bs_filter = balance_sheet_type_filter_sql(schema)
    group_expr = balance_sheet_group_expr(schema)
    sql = f"""
        SELECT
            {group_expr} AS internal_group,
            aa.id AS account_id,
            aa.code AS account_code,
            aa.name AS account_name,
            COALESCE(SUM(aml.debit), 0) AS debit_sum,
            COALESCE(SUM(aml.credit), 0) AS credit_sum,
            COALESCE(SUM(aml.debit), 0) - COALESCE(SUM(aml.credit), 0) AS balance_sum
        FROM account_move_line aml
        INNER JOIN account_move am ON aml.move_id = am.id
        INNER JOIN account_account aa ON aml.account_id = aa.id
        LEFT JOIN account_account_type aat ON aa.user_type_id = aat.id
        WHERE am.state = 'posted'
          AND aml.company_id = %s
          AND aml.date <= %s
          AND {account_filter}
          AND {bs_filter}
        GROUP BY {group_expr}, aa.id, aa.code, aa.name
        HAVING COALESCE(SUM(aml.debit), 0) <> 0
            OR COALESCE(SUM(aml.credit), 0) <> 0
        ORDER BY {group_expr}, aa.code ASC
        LIMIT %s
    """
    cursor.execute(sql, (company_id, as_of_date, limit))
    return [dict(row) for row in cursor.fetchall()]


def execute_general_ledger_sql(
    cursor: Any,
    schema: AccountingSchema,
    *,
    company_id: int,
    date_from: str,
    date_to: str,
    account_ids: list[int] | None = None,
    limit: int = 10000,
) -> list[dict[str, Any]]:
    account_filter = account_type_filter_sql(schema)
    account_clause = ""
    params: list[Any] = [company_id, date_from, date_to]
    if account_ids:
        account_clause = " AND aml.account_id = ANY(%s)"
        params.append(account_ids)
    params.append(limit)

    sql = f"""
        SELECT
            aa.code AS account_code,
            aa.name AS account_name,
            aml.date AS line_date,
            am.name AS move_name,
            COALESCE(rp.name, '') AS partner_name,
            COALESCE(aml.debit, 0) AS debit,
            COALESCE(aml.credit, 0) AS credit
        FROM account_move_line aml
        INNER JOIN account_move am ON aml.move_id = am.id
        INNER JOIN account_account aa ON aml.account_id = aa.id
        LEFT JOIN account_account_type aat ON aa.user_type_id = aat.id
        LEFT JOIN res_partner rp ON aml.partner_id = rp.id
        WHERE am.state = 'posted'
          AND aml.company_id = %s
          AND aml.date >= %s
          AND aml.date <= %s
          AND {account_filter}
          {account_clause}
        ORDER BY aa.code ASC, aml.date ASC, aml.id ASC
        LIMIT %s
    """
    cursor.execute(sql, tuple(params))
    return [dict(row) for row in cursor.fetchall()]
