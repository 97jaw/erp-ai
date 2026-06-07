#!/usr/bin/env python3
"""Debug payslip lookup for a File ID / emp_id. Usage: ./venv/bin/python scripts/probe_hr_payslip.py 2721"""
from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))


def main() -> int:
    file_id = (sys.argv[1] if len(sys.argv) > 1 else "2721").strip()
    from gateway.main import get_adapter
    from gateway.hr_identity import discover_employee_identifier_fields, resolve_employee_by_file_id
    from gateway.hr_payroll_tools import fetch_payslips_by_file_id

    adapter = get_adapter()
    print("File ID:", file_id)
    print("Employee ID fields on Odoo:", discover_employee_identifier_fields(adapter))
    employee, match = resolve_employee_by_file_id(adapter, file_id)
    print("Employee:", json.dumps(employee, default=str, indent=2) if employee else None)
    print("Match:", match)
    result = fetch_payslips_by_file_id(adapter, file_id, limit=5, employee=employee)
    print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
