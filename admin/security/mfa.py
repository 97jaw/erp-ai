from __future__ import annotations

import pyotp

from admin.security.crypto import decrypt_value, encrypt_value

ISSUER = "Elrace OOA"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_mfa_secret(secret: str) -> str:
    return encrypt_value(secret)


def decrypt_mfa_secret(stored: str) -> str:
    return decrypt_value(stored)


def build_provisioning_uri(*, secret: str, account_name: str, issuer: str = ISSUER) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def verify_totp_code(*, secret: str, code: str, valid_window: int = 1) -> bool:
    normalized = (code or "").strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    return pyotp.TOTP(secret).verify(normalized, valid_window=valid_window)
