"""Firebase ID token verification.

Production: backend trusts only Firebase Auth. ID tokens are RS256 JWTs signed by Google.
We expose `verify_firebase_token` as a FastAPI dependency that tests can override
without ever contacting Firebase.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Header, HTTPException, status

from .config import get_settings

logger = logging.getLogger(__name__)

_initialized = False


def _init_firebase() -> None:
    """Lazy-init firebase_admin once at first verify call."""
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    if not settings.firebase_credentials_path:
        logger.warning("FIREBASE_CREDENTIALS_PATH unset; verify will fail until configured.")
        _initialized = True
        return
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(settings.firebase_credentials_path))
    _initialized = True


def verify_firebase_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, Any]:
    """Decode the bearer Firebase ID token. Override this in tests via dependency_overrides.

    DEV ESCAPE HATCH: when ENVIRONMENT=dev (the default for local stacks) and the bearer is
    the literal string ``demo-token``, return a fake decoded payload representing a demo user.
    This makes the no-Firebase compose stack usable end-to-end for screenshots / smoke tests
    without setting up Firebase. Production deployments should set ENVIRONMENT=prod.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty bearer token")

    settings = get_settings()
    if settings.environment == "dev" and token == "demo-token":
        return {
            "uid": "demo-uid",
            "email": "demo@smartcalories.local",
            "name": "Demo",
            "role": "user",
        }

    _init_firebase()
    from firebase_admin import auth as fb_auth  # local import keeps import-time cheap

    try:
        return fb_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 — Firebase raises a small zoo of exception types
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
