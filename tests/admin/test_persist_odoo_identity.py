"""Test _persist_odoo_identity with asyncpg.Record-like read-only mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeRecord:
    """Simulate asyncpg.Record: read-only mapping."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getitem__(self, key: str):
        return self._data[key]

    def get(self, key: str, default=None):
        return self._data.get(key, default)


@pytest.mark.asyncio
async def test_persist_odoo_identity_does_not_mutate_readonly_user() -> None:
    from admin.auth.service import AuthService

    users = MagicMock()
    users.set_odoo_identity = AsyncMock()

    svc = AuthService.__new__(AuthService)
    svc._users = users

    user = FakeRecord({"id": 1, "file_id": "2721", "odoo_user_id": None})

    verified = {
        "file_id": "2721",
        "odoo_user_id": 4291,
        "employee_id": 100,
        "name": "Test",
        "language": "en",
    }

    await svc._persist_odoo_identity(user, verified)

    users.set_odoo_identity.assert_called_once()
    assert user["odoo_user_id"] is None
