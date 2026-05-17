from __future__ import annotations

import os

import pytest

requires_auth = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"),
    reason="OOA_DB_URL and JWT_SECRET required for auth integration tests",
)


@pytest.mark.asyncio
@requires_auth
async def test_login_super_admin_jwt() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db

    service = await AuthService.create()
    try:
        result = await service.login("2721", ip_address="127.0.0.1")
        assert result["status"] == "success"
        assert result["session_id"] == result["access_token"]
        assert "." in result["access_token"]
        assert "super_admin" in result["roles"]
        assert len(result["permissions"]) >= 30

        profile = await service.get_profile_from_token(result["access_token"])
        assert profile["file_id"] == "2721"

        await service.logout(result["access_token"])
        with pytest.raises(Exception):
            await service.get_profile_from_token(result["access_token"])
    finally:
        await close_admin_db()


def test_jwt_roundtrip() -> None:
    os.environ.setdefault("JWT_SECRET", "test-secret-for-unit")
    from admin.auth.jwt_tokens import create_access_token, decode_token, hash_token

    token, _expires = create_access_token(user_id=1, file_id="2721")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "1"
    assert payload["fid"] == "2721"
    assert len(hash_token(token)) == 64
