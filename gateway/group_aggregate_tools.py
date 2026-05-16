from __future__ import annotations

from typing import Any

from adapters.v14.connector import OdooV14Adapter
from gateway.aggregate_tools import (
    _aggregate_value,
    _label_for_group,
    _normalize_read_group_order,
    _read_group_fields,
)
from gateway.group_aggregate_domain import (
    apply_model_domain_defaults,
    build_group_aggregate_error,
    normalize_account_move_domain,
)
from gateway.tool_input_normalization import normalize_group_aggregate_input
from gateway.quality_validation import is_suspicious_group_result

MAX_GROUP_LIMIT = 200
DEFAULT_GROUP_LIMIT = 50


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], int):
        return [value[0], value[1]]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _run_group_query(
    adapter: OdooV14Adapter,
    *,
    model: str,
    domain: list[Any],
    group_by: list[str],
    aggregates: list[Any],
    order_by: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    if len(group_by) == 1:
        return _single_level_group(
            adapter,
            model=model,
            domain=domain,
            group_by=group_by,
            aggregates=aggregates,
            order_by=order_by,
            limit=limit,
        )
    return _recursive_group_by(
        adapter,
        model=model,
        domain=domain,
        group_by=group_by,
        aggregates=aggregates,
        order_by=order_by,
        limit=limit,
    )


def _clean_group_row(
    row: dict[str, Any],
    group_by: list[str],
    aggregates: list[Any],
) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if key.startswith("__"):
            clean[key.lstrip("_")] = _serialize_value(value)
        else:
            clean[key] = _serialize_value(value)

    for spec in aggregates:
        clean[str(spec)] = _aggregate_value(row, spec)

    if group_by:
        clean["group_label"] = _label_for_group(row, group_by[0].split(":")[0])
    return clean


def _apply_having(groups: list[dict[str, Any]], having: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not having:
        return groups

    operators = {
        ">": lambda left, right: left > right,
        "<": lambda left, right: left < right,
        ">=": lambda left, right: left >= right,
        "<=": lambda left, right: left <= right,
        "=": lambda left, right: left == right,
        "!=": lambda left, right: left != right,
    }

    filtered: list[dict[str, Any]] = []
    for group in groups:
        keep = True
        for field, condition in having.items():
            if isinstance(condition, list) and len(condition) == 2:
                operator, expected = condition
                actual = float(group.get(field, group.get(field.split(":")[0], 0)) or 0)
                try:
                    expected_value = float(expected)
                except (TypeError, ValueError):
                    expected_value = expected
                if operator not in operators or not operators[operator](actual, expected_value):
                    keep = False
                    break
        if keep:
            filtered.append(group)
    return filtered


def _single_level_group(
    adapter: OdooV14Adapter,
    *,
    model: str,
    domain: list[Any],
    group_by: list[str],
    aggregates: list[Any],
    order_by: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    fields = _read_group_fields(group_by, aggregates)
    order = _normalize_read_group_order(order_by, group_by, aggregates)
    try:
        rows = adapter.read_group(
            model=model,
            domain=domain,
            fields=fields,
            groupby=group_by,
            limit=limit,
            order=order,
        )
    except Exception:
        rows = adapter.read_group(
            model=model,
            domain=domain,
            fields=fields,
            groupby=group_by,
            limit=limit,
            order=None,
        )
    return [_clean_group_row(row, group_by, aggregates) for row in rows]


def _recursive_group_by(
    adapter: OdooV14Adapter,
    *,
    model: str,
    domain: list[Any],
    group_by: list[str],
    aggregates: list[Any],
    order_by: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    first = group_by[0]
    rest = group_by[1:]
    top_groups = _single_level_group(
        adapter,
        model=model,
        domain=domain,
        group_by=[first],
        aggregates=aggregates,
        order_by=order_by,
        limit=limit,
    )

    if not rest:
        return top_groups

    result: list[dict[str, Any]] = []
    for group in top_groups:
        sub_domain = list(domain)
        sub_domain.extend(group.get("domain") or group.get("__domain") or [])
        children = _recursive_group_by(
            adapter,
            model=model,
            domain=sub_domain,
            group_by=rest,
            aggregates=aggregates,
            order_by=order_by,
            limit=limit,
        )
        group["children"] = children
        result.append(group)
    return result


def _try_remote_group_and_aggregate(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        remote = adapter.call_method(
            "project.financial.service",
            "ai_group_and_aggregate",
            [
                tool_input.get("model"),
                tool_input.get("domain") or [],
                tool_input.get("group_by") or [],
                tool_input.get("aggregates") or [],
                tool_input.get("order_by"),
                tool_input.get("limit", DEFAULT_GROUP_LIMIT),
                tool_input.get("having"),
            ],
        )
    except Exception:
        return None

    if isinstance(remote, dict) and remote.get("groups") is not None:
        return remote
    return None


def group_and_aggregate(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    tool_input = normalize_group_aggregate_input(tool_input)
    model = tool_input.get("model")
    group_by = tool_input.get("group_by") or []
    if not model:
        return {"error": "missing_model", "message": "model is required for group_and_aggregate"}
    if not group_by:
        return {"error": "missing_group_by", "message": "group_by is required for group_and_aggregate"}

    domain = apply_model_domain_defaults(
        adapter,
        model,
        normalize_account_move_domain(adapter, model, list(tool_input.get("domain") or [])),
    )
    aggregates = list(tool_input.get("aggregates") or [])
    if not aggregates:
        aggregates = ["id:count"]

    limit = min(int(tool_input.get("limit") or DEFAULT_GROUP_LIMIT), MAX_GROUP_LIMIT)
    order_by = tool_input.get("order_by")
    quality_warning = None

    remote = _try_remote_group_and_aggregate(
        adapter,
        {**tool_input, "domain": domain},
    )
    if remote is not None and not remote.get("error"):
        return remote

    try:
        groups = _run_group_query(
            adapter,
            model=model,
            domain=domain,
            group_by=group_by,
            aggregates=aggregates,
            order_by=order_by,
            limit=limit,
        )
        if is_suspicious_group_result({"groups": groups, "aggregates": aggregates}):
            relaxed_domain = [
                condition
                for condition in domain
                if not (isinstance(condition, (list, tuple)) and condition and condition[0] == "state")
            ]
            if relaxed_domain != domain:
                groups = _run_group_query(
                    adapter,
                    model=model,
                    domain=relaxed_domain,
                    group_by=group_by,
                    aggregates=aggregates,
                    order_by=order_by,
                    limit=limit,
                )
            if is_suspicious_group_result({"groups": groups, "aggregates": aggregates}):
                quality_warning = (
                    "No meaningful posted values were found for that grouping. "
                    "Try a wider date range or confirm the invoice filters."
                )
    except Exception as exc:
        return build_group_aggregate_error(
            error="group_and_aggregate_failed",
            message=str(exc),
            model=model,
            domain=domain,
            group_by=group_by,
            aggregates=aggregates,
            adapter=adapter,
        )

    groups = _apply_having(groups, tool_input.get("having"))

    return {
        "model": model,
        "group_by": group_by,
        "aggregates": aggregates,
        "filters_applied": domain,
        "total_groups": len(groups),
        "groups": groups,
        "row_count": len(groups),
        "synthesized": True,
        "source": "read_group",
        "quality_warning": quality_warning,
    }
