"""Tests for gateway.core.capability_manifest."""

from gateway.core.capability_manifest import CAPABILITY_MANIFEST


def test_can_do_financial_pandl_returns_true():
    assert CAPABILITY_MANIFEST.can_do("financial.pandl") is True


def test_can_do_hr_payslips_returns_false():
    assert CAPABILITY_MANIFEST.can_do("hr.payslips") is False


def test_can_do_fake_capability_returns_false():
    assert CAPABILITY_MANIFEST.can_do("fake.capability") is False


def test_status_of_hr_payslips_returns_unavailable():
    assert CAPABILITY_MANIFEST.status_of("hr.payslips") == "unavailable"


def test_status_of_outlook_email_returns_coming_soon():
    assert CAPABILITY_MANIFEST.status_of("integrations.outlook_email") == "coming_soon"


def test_status_of_financial_pandl_returns_available():
    assert CAPABILITY_MANIFEST.status_of("financial.pandl") == "available"


def test_status_of_random_capability_returns_unknown():
    assert CAPABILITY_MANIFEST.status_of("something.random") == "unknown"


def test_summary_contains_cannot_do_section():
    summary = CAPABILITY_MANIFEST.summary()
    assert "WHAT YOU CANNOT DO" in summary


def test_summary_contains_honest_instruction_not_to_fabricate_errors():
    summary = CAPABILITY_MANIFEST.summary()
    assert "DO NOT FABRICATE FAKE ERRORS" in summary


def test_hr_payslips_unavailable_entry_has_hr_portal_alternative():
    payslips = next(
        capability
        for capability in CAPABILITY_MANIFEST.unavailable
        if capability.code == "hr.payslips"
    )
    assert payslips.alternative is not None
    assert "HR portal" in payslips.alternative


def test_manifest_has_at_least_ten_available_capabilities():
    assert len(CAPABILITY_MANIFEST.available) >= 10


def test_manifest_has_at_least_five_unavailable_capabilities():
    assert len(CAPABILITY_MANIFEST.unavailable) >= 5
