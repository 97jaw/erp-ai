"""Phase M2 — HR module context in system prompt."""

from gateway.core.hr_module_context import HR_MODULE_PROMPT_SECTION
from gateway.main import _compose_system_prompt_sections


def test_hr_section_constant_has_key_models() -> None:
    assert "=== ELRACE HR MODULE ===" in HR_MODULE_PROMPT_SECTION
    assert "hr.employee" in HR_MODULE_PROMPT_SECTION
    assert "employee.requests" in HR_MODULE_PROMPT_SECTION
    assert "x_attendance_type" in HR_MODULE_PROMPT_SECTION
    assert "is_labor=True" in HR_MODULE_PROMPT_SECTION


def test_composed_system_prompt_includes_hr_section_after_relationship() -> None:
    prompt = _compose_system_prompt_sections("2026-06-11")
    rel_end = prompt.index("=== END RELATIONSHIP CONTEXT ===")
    hr_start = prompt.index("=== ELRACE HR MODULE ===")
    hr_end = prompt.index("=== END HR CONTEXT ===")
    financial = prompt.index("GROUPING AND FILTERING:")
    assert rel_end < hr_start < hr_end < financial
