from __future__ import annotations

from gateway.agent.attachment_fast_path import is_attachment_list_query
from gateway.attachments.visualization import (
    build_file_list_visualization,
    file_list_summary_text,
    sanitize_visualization_for_persist,
)
from gateway.ephemeral_files import EphemeralFileStore
from gateway.tools.list_attachments import execute_list_attachments


class _FakeAdapter:
    def safe_search_read(self, model, domain, fields, limit=1, order=None, offset=0):
        if model == "project.project":
            return [{"id": 1374, "name": "National Guard Hospital", "agreement_id": [88, "AG-88"]}]
        return []

    def read_project_attachments(self, project_id, *, limit=20, offset=0):
        return {
            "rows": [{"id": 501, "name": "WO Folder", "file_count": 2}],
            "total_count": 1,
            "source_model": "project.attachment",
        }

    def read_agreement_attachments(self, agreement_id, *, limit=20, offset=0):
        return {"rows": [], "total_count": 0, "source_model": "agreement.attachment"}

    def read_ir_attachments(self, **kwargs):
        res_model = kwargs.get("res_model")
        if res_model == "project.attachment":
            return {
                "rows": [
                    {
                        "id": 9001,
                        "name": "LPO.pdf",
                        "mimetype": "application/pdf",
                        "file_size": 2048,
                        "create_date": "2026-06-01",
                        "create_uid": [1, "Admin"],
                        "res_model": "project.attachment",
                        "res_id": 501,
                    }
                ],
                "total_count": 1,
            }
        if res_model == "project.project":
            return {"rows": [], "total_count": 0}
        return {"rows": [], "total_count": 0}


def setup_function() -> None:
    EphemeralFileStore.clear_for_tests()


def test_is_attachment_list_query_matches_files_for_project() -> None:
    assert is_attachment_list_query(
        "show me files for project national guard — National Guard (ID: 1374)"
    )
    assert is_attachment_list_query("project attachments")


def test_execute_list_attachments_collects_ir_files_from_project_folders() -> None:
    result = execute_list_attachments({"project_id": 1374, "limit": 20}, _FakeAdapter())
    assert result["status"] == "success"
    assert result["total_count"] == 1
    assert result["files"][0]["name"] == "LPO.pdf"
    assert result["files"][0]["odoo_attachment_id"] == 9001


def test_file_list_summary_text_is_short_when_visual_present() -> None:
    text = file_list_summary_text("Al Hili Healthcare Center — documents", 1)
    assert "W.O" not in text
    assert "1" in text
    assert "Al Hili" in text


def test_build_file_list_visualization_registers_tokens() -> None:
    payload = {
        "status": "success",
        "label": "Docs",
        "total_count": 1,
        "files": [
            {
                "odoo_attachment_id": 11,
                "name": "a.pdf",
                "mimetype": "application/pdf",
                "size_bytes": 100,
            }
        ],
    }
    visual = build_file_list_visualization(payload, session_id="thread-1")
    assert visual is not None
    assert visual["visual_type"] == "FILE_LIST"
    assert visual["ephemeral"] is True
    token = visual["data"]["files"][0]["download_token"]
    assert EphemeralFileStore.resolve(token) is not None


def test_sanitize_visualization_for_persist_strips_files() -> None:
    visual = {
        "visual_type": "FILE_LIST",
        "ephemeral": True,
        "data": {"files": [{"name": "a.pdf", "download_token": "secret"}]},
    }
    stripped = sanitize_visualization_for_persist(visual)
    assert stripped is not None
    assert "files" not in stripped["data"]
    assert stripped["data"]["file_count"] == 1
