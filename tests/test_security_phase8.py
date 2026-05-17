from __future__ import annotations

import os

import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"),
    reason="OOA_DB_URL and JWT_SECRET required",
)


def test_password_hash_roundtrip() -> None:
    from admin.security.passwords import hash_password, verify_password

    hashed = hash_password("Str0ng-Pass!")
    assert verify_password("Str0ng-Pass!", hashed)
    assert not verify_password("wrong", hashed)


def test_totp_generate_and_verify() -> None:
    from admin.security.mfa import generate_totp_secret, verify_totp_code
    import pyotp

    secret = generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret=secret, code=code)


def test_rate_limit_login_ip() -> None:
    from admin.security.rate_limit import RateLimitExceeded, check_login_ip

    ip = "test-rate-limit-ip-unique"
    for _ in range(5):
        check_login_ip(ip)
    with pytest.raises(RateLimitExceeded):
        check_login_ip(ip)


def test_mfa_encrypt_roundtrip() -> None:
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-phase8")
    from admin.security.mfa import decrypt_mfa_secret, encrypt_mfa_secret, generate_totp_secret

    secret = generate_totp_secret()
    stored = encrypt_mfa_secret(secret)
    assert decrypt_mfa_secret(stored) == secret


@pytest.mark.asyncio
@requires_db
async def test_password_reset_flow() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.users import UserRepository
    from admin.security.passwords import generate_reset_token, hash_password, hash_reset_token, verify_password

    service = await AuthService.create()
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="phase8-reset-user",
            name="Phase 8 Reset",
            email="phase8reset@test.com",
        )
        plain, token_hash = generate_reset_token()
        from datetime import datetime, timedelta, timezone

        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await users.set_password_reset(user_id, token_hash, expires)
        row = await users.find_by_reset_token(hash_reset_token(plain))
        assert row is not None
        await users.set_password_hash(user_id, hash_password("NewPass123!"))
        creds = await users.get_auth_credentials(user_id)
        assert verify_password("NewPass123!", creds["password_hash"])
        await users.clear_password_reset(user_id)
        await users.soft_delete(user_id)
        user_id = None
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()
