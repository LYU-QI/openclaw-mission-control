# ruff: noqa: INP001
"""Tests for app secret encryption helpers."""

from __future__ import annotations

from app.core.secrets import decrypt_secret, encrypt_secret


def test_encrypt_and_decrypt_roundtrip() -> None:
    plain = "feishu-secret-value"
    encrypted = encrypt_secret(plain)
    assert encrypted != plain
    assert encrypted.startswith("enc::")
    assert decrypt_secret(encrypted) == plain


def test_decrypt_legacy_plaintext_passthrough() -> None:
    plain = "legacy-plaintext-secret"
    assert decrypt_secret(plain) == plain
