"""Tests for gateway.core.capability_manifest."""

from gateway.core.capability_manifest import CAPABILITY_MANIFEST


def test_can_do_financial_pandl_returns_true():
    assert CAPABILITY_MANIFEST.can_do("financial.pandl") is True


def test_can_do_universal_odoo_read_returns_true():
    assert CAPABILITY_MANIFEST.can_do("universal.odoo_read") is True


def test_can_do_hr_payslips_returns_true_after_open_gates():
    assert CAPABILITY_MANIFEST.can_do("hr.payslips") is True


def test_can_do_write_create_returns_false():
    assert CAPABILITY_MANIFEST.can_do("write.create_record") is False


def test_can_do_fake_capability_returns_false():
    assert CAPABILITY_MANIFEST.can_do("fake.capability") is False


def test_status_of_hr_payslips_returns_available():
    assert CAPABILITY_MANIFEST.status_of("hr.payslips") == "available"


def test_status_of_write_create_returns_unavailable():
    assert CAPABILITY_MANIFEST.status_of("write.create_record") == "unavailable"


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


def test_summary_mentions_query_odoo_for_reads():
    summary = CAPABILITY_MANIFEST.summary()
    assert "query_odoo" in summary


def test_write_create_unavailable_entry_has_odoo_alternative():
    create = next(
        capability
        for capability in CAPABILITY_MANIFEST.unavailable
        if capability.code == "write.create_record"
    )
    assert create.alternative is not None
    assert "Odoo" in create.alternative


def test_manifest_has_at_least_ten_available_capabilities():
    assert len(CAPABILITY_MANIFEST.available) >= 10


def test_manifest_unavailable_is_writes_and_non_erp_only():
    codes = {capability.code for capability in CAPABILITY_MANIFEST.unavailable}
    assert codes.issubset(
        {
            "write.create_record",
            "write.update_record",
            "write.delete_record",
            "write.approve_transactions",
            "non_erp.weather",
            "non_erp.web_browsing",
            "non_erp.general_knowledge",
        }
    )
    assert "hr.payslips" not in codes
    assert "inventory.stock" not in codes
