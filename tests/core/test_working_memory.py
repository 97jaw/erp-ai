"""Tests for gateway.core.working_memory."""

from gateway.core.working_memory import WorkingMemory


def test_remember_entity_adds_to_recent_entities():
    memory = WorkingMemory()
    entity = {"name": "Zayidia Boys School", "id": 14549}

    memory.remember_entity("project", entity)

    assert len(memory.recent_entities) == 1
    assert memory.recent_entities[0]["type"] == "project"
    assert memory.recent_entities[0]["data"] == entity


def test_find_entity_finds_exact_match_by_name():
    memory = WorkingMemory()
    entity = {"name": "Zayidia Boys School", "id": 14549}
    memory.remember_entity("project", entity)

    found = memory.find_entity("Zayidia Boys School")

    assert found == entity


def test_find_entity_finds_partial_match():
    memory = WorkingMemory()
    entity = {"name": "Zayidia Girls School Al Ain", "id": 14610}
    memory.remember_entity("project", entity)

    found = memory.find_entity("Girls School")

    assert found == entity


def test_find_entity_filtered_by_type_works_correctly():
    memory = WorkingMemory()
    project = {"name": "National Guard HQ", "id": 1001}
    partner = {"name": "National Guard", "id": 2001}
    memory.remember_entity("project", project)
    memory.remember_entity("partner", partner)

    found_project = memory.find_entity("National Guard", entity_type="project")
    found_partner = memory.find_entity("National Guard", entity_type="partner")

    assert found_project == project
    assert found_partner == partner


def test_memory_caps_at_ten_entities_oldest_dropped():
    memory = WorkingMemory()

    for index in range(12):
        memory.remember_entity("project", {"name": f"Project {index}", "id": index})

    assert len(memory.recent_entities) == 10
    assert memory.recent_entities[0]["data"]["id"] == 2
    assert memory.recent_entities[-1]["data"]["id"] == 11


def test_find_entity_returns_none_when_no_match():
    memory = WorkingMemory()
    memory.remember_entity("project", {"name": "Zayidia Boys School", "id": 14549})

    assert memory.find_entity("Nonexistent Project") is None


def test_session_facts_can_store_and_retrieve_key_value():
    memory = WorkingMemory()
    memory.session_facts["active_project_id"] = 14549

    assert memory.session_facts["active_project_id"] == 14549


def test_summary_returns_non_empty_string():
    memory = WorkingMemory()
    memory.remember_entity("project", {"name": "Zayidia Boys School", "id": 14549})
    memory.session_facts["currency"] = "AED"

    summary = memory.summary()

    assert isinstance(summary, str)
    assert summary.strip()
    assert "RECENT ENTITIES" in summary
    assert "SESSION FACTS" in summary


def test_successful_strategies_can_be_stored_and_retrieved():
    memory = WorkingMemory()
    memory.successful_strategies["financial.pandl"] = "fetch_report_then_summarize"

    assert memory.successful_strategies["financial.pandl"] == "fetch_report_then_summarize"


def test_most_recently_added_entity_returned_first_in_find_entity():
    memory = WorkingMemory()
    older = {"name": "National Guard Contract A", "id": 3001}
    newer = {"name": "National Guard Contract B", "id": 3002}
    memory.remember_entity("project", older)
    memory.remember_entity("project", newer)

    found = memory.find_entity("National Guard")

    assert found == newer
