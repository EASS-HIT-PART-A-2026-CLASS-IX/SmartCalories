"""Symmetric encryption for user-supplied secrets (e.g. a personal Gemini API key).

User API keys must be stored so we can *use* them (not just verify a hash), so we encrypt at
rest with Fernet (AES-128-CBC + HMAC). The Fernet key is derived from `settings.secret_key` via
SHA-256, so rotating the app secret invalidates all stored keys (users would re-enter them).

In prod `SECRET_KEY` MUST be set. In dev/test we fall back to a fixed insecure constant so the
feature works without configuration — a warning is logged so it isn't shipped that way.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings

logger = logging.getLogger(__name__)

_DEV_FALLBACK_SECRET = "smartcalories-dev-insecure-secret-change-me"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.secret_key
    if not secret:
        logger.warning(
            "SECRET_KEY not set — encrypting user API keys with an INSECURE dev fallback. "
            "Set SECRET_KEY in production."
        )
        secret = _DEV_FALLBACK_SECRET
    # Fernet needs a 32-byte urlsafe-base64 key; derive one deterministically from the secret.
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns an opaque token (str)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str | None:
    """Decrypt a stored token. Returns None if it can't be decrypted (e.g. secret rotated)."""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        logger.warning("failed to decrypt a stored secret (key rotated or corrupt token)")
        return None
