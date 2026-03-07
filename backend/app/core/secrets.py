"""Utilities for encrypting/decrypting application secrets at rest."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import settings

_ENCRYPTED_PREFIX = "enc::"


def _normalize_fernet_key(raw_key: str) -> bytes:
    candidate = raw_key.strip().encode("utf-8")
    try:
        Fernet(candidate)
        return candidate
    except Exception:
        digest = hashlib.sha256(candidate).digest()
        return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    # In production, set APP_SECRET_ENCRYPTION_KEY explicitly.
    configured = settings.app_secret_encryption_key.strip()
    if configured:
        return Fernet(_normalize_fernet_key(configured))
    # Dev/test fallback keeps local flows working without extra setup.
    seed = f"{settings.base_url}|{settings.local_auth_token or 'dev-seed'}"
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest()))


def encrypt_secret(value: str) -> str:
    """Encrypt plaintext and mark it with a prefix for backward compatibility."""
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Decrypt secret value; returns legacy plaintext values as-is."""
    if not value.startswith(_ENCRYPTED_PREFIX):
        return value
    token = value[len(_ENCRYPTED_PREFIX) :]
    return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
