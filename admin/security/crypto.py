from __future__ import annotations

import base64
import hashlib
import os


def _fernet_key() -> bytes:
    raw = os.environ.get("MFA_ENCRYPTION_KEY", "").strip() or os.environ.get("JWT_SECRET", "").strip()
    if not raw:
        raise RuntimeError("MFA_ENCRYPTION_KEY or JWT_SECRET required for MFA encryption")
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plain: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(_fernet_key()).encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_value(cipher: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(_fernet_key()).decrypt(cipher.encode("ascii")).decode("utf-8")
