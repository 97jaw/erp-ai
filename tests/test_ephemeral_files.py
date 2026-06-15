from __future__ import annotations

import time

from gateway.ephemeral_files import EphemeralFileStore


def setup_function() -> None:
    EphemeralFileStore.clear_for_tests()


def test_register_and_resolve_download_token() -> None:
    registered = EphemeralFileStore.register(
        session_id="sess-1",
        files=[
            {
                "odoo_attachment_id": 42,
                "name": "spec.pdf",
                "mimetype": "application/pdf",
                "size_bytes": 1024,
            }
        ],
        ttl_seconds=120,
    )
    assert len(registered) == 1
    token = registered[0]["download_token"]
    ref = EphemeralFileStore.resolve(token)
    assert ref is not None
    assert ref.odoo_attachment_id == 42
    assert ref.session_id == "sess-1"


def test_expired_token_is_removed() -> None:
    registered = EphemeralFileStore.register(
        session_id="sess-2",
        files=[{"odoo_attachment_id": 7, "name": "a.txt", "mimetype": "text/plain"}],
        ttl_seconds=1,
    )
    token = registered[0]["download_token"]
    time.sleep(1.1)
    assert EphemeralFileStore.resolve(token) is None


def test_cleanup_session_removes_tokens() -> None:
    registered = EphemeralFileStore.register(
        session_id="sess-3",
        files=[{"odoo_attachment_id": 9, "name": "b.pdf", "mimetype": "application/pdf"}],
    )
    token = registered[0]["download_token"]
    assert EphemeralFileStore.cleanup_session("sess-3") == 1
    assert EphemeralFileStore.resolve(token) is None
