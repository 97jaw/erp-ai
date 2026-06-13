"""Phase M6 — Payroll module context in system prompt."""

from gateway.core.payroll_module_context import PAYROLL_MODULE_PROMPT_SECTION
from gateway.main import _compose_system_prompt_sections


def test_payroll_section_constant_has_key_models() -> None:
    assert "=== ELRACE PAYROLL MODULE ===" in PAYROLL_MODULE_PROMPT_SECTION
    assert "hr.payslip.cost.allocation" in PAYROLL_MODULE_PROMPT_SECTION
    assert "labor_snapshot_total_salary" in PAYROLL_MODULE_PROMPT_SECTION
    assert "staff_snapshot_total_salary" in PAYROLL_MODULE_PROMPT_SECTION


def test_composed_system_prompt_includes_payroll_section_after_hr() -> None:
    prompt = _compose_system_prompt_sections("2026-06-11")
    hr_end = prompt.index("=== END HR CONTEXT ===")
    payroll_start = prompt.index("=== ELRACE PAYROLL MODULE ===")
    payroll_end = prompt.index("=== END PAYROLL CONTEXT ===")
    financial = prompt.index("GROUPING AND FILTERING:")
    assert hr_end < payroll_start < payroll_end < financial
