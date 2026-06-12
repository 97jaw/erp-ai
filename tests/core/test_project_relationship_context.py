"""Phase R2 — project relationship context in system prompt."""

from gateway.core.project_relationship_context import PROJECT_RELATIONSHIP_PROMPT_SECTION
from gateway.main import _compose_system_prompt_sections


def test_relationship_section_constant_has_key_models() -> None:
    assert "project.project.agreement_id → agreement" in PROJECT_RELATIONSHIP_PROMPT_SECTION
    assert "project.attachment" in PROJECT_RELATIONSHIP_PROMPT_SECTION
    assert "agreement.attachment" in PROJECT_RELATIONSHIP_PROMPT_SECTION
    assert "projects with no attachments" in PROJECT_RELATIONSHIP_PROMPT_SECTION


def test_composed_system_prompt_includes_relationship_section() -> None:
    prompt = _compose_system_prompt_sections("2026-06-11")
    assert "=== PROJECT RELATIONAL MODEL ===" in prompt
    assert "=== END RELATIONSHIP CONTEXT ===" in prompt
    assert "lead_attachment_type" in prompt
