"""Tests for gateway.core.intent_analyzer data models."""

from gateway.core.intent_analyzer import Ambiguity, EntityReference, Intent


def test_intent_can_be_instantiated_with_all_required_fields() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show P&L for last quarter",
        entities=[
            EntityReference(type="period", value="last quarter", confidence=0.95),
        ],
        implicit_requirements=["Use last 3 months if period unspecified"],
        ambiguities=[
            Ambiguity(
                type="period",
                description="Quarter not explicitly dated",
                severity="low",
            ),
        ],
        expected_output="summary",
        urgency="normal",
        estimated_complexity="simple",
        requires_clarification=False,
        clarification_question=None,
        out_of_scope=False,
        out_of_scope_reason=None,
    )

    assert intent.primary_action == "fetch_data"
    assert intent.specific_intent == "Show P&L for last quarter"


def test_entity_reference_has_type_value_confidence_fields() -> None:
    entity = EntityReference(type="project", value="Zayidia Boys School", confidence=0.92)

    assert entity.type == "project"
    assert entity.value == "Zayidia Boys School"
    assert entity.confidence == 0.92


def test_ambiguity_has_type_description_severity_fields() -> None:
    ambiguity = Ambiguity(
        type="project",
        description="Multiple National Guard projects match",
        severity="medium",
    )

    assert ambiguity.type == "project"
    assert ambiguity.description == "Multiple National Guard projects match"
    assert ambiguity.severity == "medium"


def test_intent_defaults_requires_clarification_and_out_of_scope_false() -> None:
    intent = Intent(
        primary_action="ask_question",
        subject_area="general",
        specific_intent="What can you do?",
    )

    assert intent.requires_clarification is False
    assert intent.out_of_scope is False
    assert intent.clarification_question is None
    assert intent.out_of_scope_reason is None


def test_intent_with_entities_list_works_correctly() -> None:
    entities = [
        EntityReference(type="project", value="National Guard HQ", confidence=0.88),
        EntityReference(type="period", value="YTD", confidence=0.91),
    ]
    intent = Intent(
        primary_action="analyze",
        subject_area="project",
        specific_intent="Compare project costs YTD",
        entities=entities,
    )

    assert len(intent.entities) == 2
    assert intent.entities[0].type == "project"
    assert intent.entities[1].value == "YTD"


def test_intent_serializes_to_dict_cleanly_for_logging() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="Show my payslip",
        entities=[EntityReference(type="period", value="this month", confidence=0.8)],
        ambiguities=[
            Ambiguity(type="capability", description="HR payslips unavailable", severity="high"),
        ],
        out_of_scope=True,
        out_of_scope_reason="hr.payslips is unavailable",
    )

    payload = intent.to_dict()

    assert isinstance(payload, dict)
    assert payload["primary_action"] == "fetch_data"
    assert payload["out_of_scope"] is True
    assert payload["entities"][0]["type"] == "period"
    assert payload["ambiguities"][0]["severity"] == "high"
    assert payload["clarification_question"] is None


def test_intent_all_fields_accessible_as_expected() -> None:
    intent = Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue across top clients",
        entities=[EntityReference(type="partner", value="National Guard", confidence=0.9)],
        implicit_requirements=["Rank by revenue"],
        ambiguities=[Ambiguity(type="period", description="No date range given", severity="medium")],
        expected_output="chart",
        urgency="high",
        estimated_complexity="complex",
        requires_clarification=True,
        clarification_question="Which period should I compare?",
        out_of_scope=False,
        out_of_scope_reason=None,
    )

    assert intent.primary_action == "compare"
    assert intent.subject_area == "financial"
    assert intent.specific_intent == "Compare revenue across top clients"
    assert len(intent.entities) == 1
    assert intent.implicit_requirements == ["Rank by revenue"]
    assert len(intent.ambiguities) == 1
    assert intent.expected_output == "chart"
    assert intent.urgency == "high"
    assert intent.estimated_complexity == "complex"
    assert intent.requires_clarification is True
    assert intent.clarification_question == "Which period should I compare?"
    assert intent.out_of_scope is False
    assert intent.out_of_scope_reason is None
