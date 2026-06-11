#!/usr/bin/env python3
"""Introspect project-linked record models on live Odoo for Project Model Phase 2.

Discovers:
1. The custom Elrace petty cash model (via signature fields like
   petty_cash_holder_stored) and how it links to projects (header vs lines).
2. The custom staff-list model (via emp_code + project_id signature).
3. account.move project linkage + client vs LPO invoice split per project.
4. account.analytic.line (timesheets) and purchase.order project linkage.

Saves raw output under .cache/introspection/ and prints a field-map report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / ".cache" / "introspection"


def find_models_with_field(adapter: Any, field_name: str) -> list[dict[str, Any]]:
    """All models that define a field with this exact technical name."""
    return adapter.safe_search_read(
        "ir.model.fields",
        [["name", "=", field_name]],
        ["model", "name", "ttype", "relation", "field_description"],
        limit=40,
    )


def model_fields(adapter: Any, model: str) -> dict[str, Any]:
    return adapter.call_method(
        model,
        "fields_get",
        [],
        {"attributes": ["string", "type", "relation"]},
    )


def read_one(
    adapter: Any,
    model: str,
    domain: list[Any],
    order: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any] | None:
    # Full reads crash on broken Elrace computed fields — always pass a
    # curated field list when sampling custom models.
    kwargs: dict[str, Any] = {"limit": 1}
    if order:
        kwargs["order"] = order
    ids = adapter.call_method(model, "search", [domain], kwargs)
    if not ids:
        return None
    read_kwargs: dict[str, Any] = {}
    if fields:
        read_kwargs["fields"] = fields
    recs = adapter.call_method(model, "read", [ids], read_kwargs)
    return recs[0] if recs else None


SAMPLE_FIELDS = {
    "hr.expense": [
        "name", "seq_no", "date", "accounting_date", "employee_id", "project_id",
        "total_amount", "unit_amount", "untaxed_amount", "state", "description",
        "product_id", "sheet_id", "operating_unit_id",
    ],
    "hr.expense.sheet": [
        "name", "seq_no", "date", "accounting_date", "employee_id", "project_id",
        "total_amount", "state", "operating_unit_id", "custom_petty_cash_type",
        "petty_cash_amount", "voucher_date",
    ],
    "staff.list": [
        "project_id", "employee_id", "emp_code", "emp_name", "job_id",
        "status", "access", "create_date", "write_date",
    ],
    "project.supervisor": [
        "project_id", "employee_id", "emp_code", "emp_name", "job_id",
        "status", "access", "create_date", "write_date",
    ],
}


def count(adapter: Any, model: str, domain: list[Any]) -> int:
    return int(adapter.call_method(model, "search_count", [domain], {}))


def main() -> int:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    adapter = get_shared_odoo_adapter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("A) Locate custom models via signature fields")
    for signature in ("petty_cash_holder_stored", "custom_petty_cash_type", "emp_code"):
        hits = find_models_with_field(adapter, signature)
        models = sorted({hit["model"] for hit in hits})
        print(f"   field {signature!r} found on models: {models}")

    # Candidate staff models: emp_code + project_id on the same model.
    emp_code_models = sorted({hit["model"] for hit in find_models_with_field(adapter, "emp_code")})
    staff_candidates = []
    for model in emp_code_models:
        try:
            fields = model_fields(adapter, model)
        except Exception as exc:  # noqa: BLE001 - introspection probe
            print(f"   [skip] fields_get({model}) failed: {exc}")
            continue
        if "project_id" in fields and "employee_id" in fields:
            staff_candidates.append(model)
    print(f"\n   staff candidates (emp_code + project_id + employee_id): {staff_candidates}")

    petty_models = sorted(
        {hit["model"] for hit in find_models_with_field(adapter, "petty_cash_holder_stored")},
    )

    print("\n" + "=" * 72)
    print("B) Petty cash model details")
    for model in petty_models:
        fields = model_fields(adapter, model)
        (OUT_DIR / f"fields_{model.replace('.', '_')}.json").write_text(
            json.dumps(fields, indent=2),
        )
        interesting = [
            name for name in fields
            if any(token in name for token in ("project", "amount", "date", "state", "name", "employee", "seq"))
        ]
        print(f"   model={model} total_fields={len(fields)}")
        print(f"   interesting: {sorted(interesting)[:40]}")
        total = count(adapter, model, [])
        with_project = count(adapter, model, [["project_id", "!=", False]]) if "project_id" in fields else -1
        print(f"   records total={total} with project_id={with_project}")
        # Line model?
        line_fields = [
            (name, meta.get("relation"))
            for name, meta in fields.items()
            if meta.get("type") == "one2many"
        ]
        print(f"   one2many lines: {line_fields}")
        wanted = [name for name in SAMPLE_FIELDS.get(model, []) if name in fields]
        sample = read_one(
            adapter,
            model,
            [["project_id", "!=", False]] if "project_id" in fields else [],
            order="id desc",
            fields=wanted,
        )
        if sample:
            path = OUT_DIR / f"sample_{model.replace('.', '_')}.json"
            path.write_text(json.dumps(sample, indent=2, default=str))
            print(f"   sample saved -> {path}")
            print(f"   sample: {json.dumps(sample, default=str)[:400]}")

    print("\n" + "=" * 72)
    print("C) Staff model details")
    for model in staff_candidates:
        fields = model_fields(adapter, model)
        (OUT_DIR / f"fields_{model.replace('.', '_')}.json").write_text(
            json.dumps(fields, indent=2),
        )
        print(f"   model={model} field_count={len(fields)}")
        print(f"   fields: {sorted(fields)}")
        total = count(adapter, model, [])
        print(f"   records total={total}")
        wanted = [name for name in SAMPLE_FIELDS.get(model, []) if name in fields]
        sample = read_one(adapter, model, [], order="id desc", fields=wanted)
        if sample:
            print(f"   sample: {json.dumps(sample, default=str)[:400]}")

    print("\n" + "=" * 72)
    print("D) account.move project linkage")
    am_fields = model_fields(adapter, "account.move")
    project_fields = [name for name in am_fields if "project" in name]
    print(f"   project-ish fields on account.move: {sorted(project_fields)}")
    linked = count(adapter, "account.move", [["project_id", "!=", False]])
    print(f"   moves with project_id set: {linked}")
    # Find busiest linked projects to use as live test targets.
    recent = adapter.safe_search_read(
        "account.move",
        [["project_id", "!=", False], ["state", "=", "posted"]],
        ["project_id", "move_type"],
        limit=80,
    )
    by_project: dict[tuple[int, str], int] = {}
    for move in recent:
        m2o = move.get("project_id")
        if isinstance(m2o, (list, tuple)) and m2o:
            by_project[(m2o[0], str(m2o[1]))] = by_project.get((m2o[0], str(m2o[1])), 0) + 1
    top = sorted(by_project.items(), key=lambda item: -item[1])[:5]
    print(f"   busiest linked projects (recent sample): {top}")
    if top:
        pid = top[0][0][0]
        for move_type in ("out_invoice", "in_invoice"):
            n = count(
                adapter,
                "account.move",
                [["project_id", "=", pid], ["move_type", "=", move_type], ["state", "!=", "cancel"]],
            )
            print(f"   project {pid}: {move_type} count={n}")
        sample = read_one(
            adapter,
            "account.move",
            [["project_id", "=", pid], ["state", "!=", "cancel"]],
            order="invoice_date desc",
            fields=[
                "name", "move_type", "invoice_date", "partner_id", "amount_total",
                "amount_residual", "payment_state", "state", "project_id", "ref",
                "invoice_origin", "lpo_no", "financial_type",
            ],
        )
        if sample:
            path = OUT_DIR / "sample_account_move_project.json"
            path.write_text(json.dumps(sample, indent=2, default=str))
            print(f"   sample saved -> {path}")

    print("\n" + "=" * 72)
    print("E) Timesheets + purchase orders linkage")
    ts_count = count(adapter, "account.analytic.line", [["project_id", "!=", False]])
    print(f"   account.analytic.line with project_id: {ts_count}")
    ts = read_one(adapter, "account.analytic.line", [["project_id", "!=", False]], order="date desc")
    if ts:
        print(f"   latest timesheet: project={ts.get('project_id')} employee={ts.get('employee_id')} "
              f"date={ts.get('date')} hours={ts.get('unit_amount')}")
    po_count = count(adapter, "purchase.order", [["project_id", "!=", False]])
    print(f"   purchase.order with project_id: {po_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
