from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AccountingSchema:
    has_internal_group: bool
    account_type_table: str
    account_type_group_column: str


def load_schema(cursor: Any) -> AccountingSchema:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'account_account_type'
        """
    )
    columns = {row["column_name"] for row in cursor.fetchall()}
    if "internal_group" in columns:
        return AccountingSchema(
            has_internal_group=True,
            account_type_table="account_account_type",
            account_type_group_column="internal_group",
        )
    return AccountingSchema(
        has_internal_group=False,
        account_type_table="account_account_type",
        account_type_group_column="type",
    )


def account_type_filter_sql(schema: AccountingSchema, alias: str = "aat") -> str:
    if schema.has_internal_group:
        return f"({alias}.internal_group IS NULL OR {alias}.internal_group NOT IN ('view'))"
    return f"({alias}.type IS NULL OR {alias}.type NOT IN ('view', 'consolidation'))"


def pandl_type_filter_sql(schema: AccountingSchema, alias: str = "aat") -> str:
    if schema.has_internal_group:
        return f"{alias}.internal_group IN ('income', 'expense')"
    return f"{alias}.type IN ('income', 'expense', 'depreciation', 'direct_cost')"


def balance_sheet_type_filter_sql(schema: AccountingSchema, alias: str = "aat") -> str:
    if schema.has_internal_group:
        return f"{alias}.internal_group IN ('asset', 'liability', 'equity')"
    return (
        f"{alias}.type IN ('receivable', 'payable', 'liquidity', 'other', "
        f"'equity', 'asset', 'liability')"
    )


def sql_internal_group_expr(schema: AccountingSchema, alias: str = "aat") -> str:
    if schema.has_internal_group:
        return f"{alias}.internal_group"
    return (
        f"CASE WHEN {alias}.type IN ('income') THEN 'income' "
        f"WHEN {alias}.type IN ('expense', 'depreciation', 'direct_cost') THEN 'expense' "
        f"ELSE NULL END"
    )


def balance_sheet_group_expr(schema: AccountingSchema, alias: str = "aat") -> str:
    if schema.has_internal_group:
        return f"{alias}.internal_group"
    return (
        f"CASE WHEN {alias}.type IN ('receivable', 'liquidity', 'other') THEN 'asset' "
        f"WHEN {alias}.type IN ('payable') THEN 'liability' "
        f"WHEN {alias}.type IN ('equity') THEN 'equity' "
        f"ELSE NULL END"
    )
