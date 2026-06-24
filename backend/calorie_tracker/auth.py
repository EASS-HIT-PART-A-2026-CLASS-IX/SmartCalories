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
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        if settings.firebase_credentials_json:
            import json
            cert = credentials.Certificate(json.loads(settings.firebase_credentials_json))
            firebase_admin.initialize_app(cert)
        elif settings.firebase_credentials_path:
            firebase_admin.initialize_app(credentials.Certificate(settings.firebase_credentials_path))
        else:
            logger.warning("Neither FIREBASE_CREDENTIALS_JSON nor FIREBASE_CREDENTIALS_PATH set; token verify will fail.")
            _initialized = True
            return
    _initialized = True


def decode_token(token: str) -> dict[str, Any]:
    """Decode a raw Firebase ID token string into its claims. Used by both the HTTP header
    dependency and the WebSocket handler (browsers can't set headers on a WS handshake, so the
    WS path passes the token as a query param and calls this directly).

    DEV ESCAPE HATCH: when ENVIRONMENT=dev and the token is the literal ``demo-token``, return a
    fake payload representing a demo user, so the no-Firebase compose stack works end-to-end.
    """
    token = (token or "").strip()
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


def verify_firebase_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, Any]:
    """Decode the bearer Firebase ID token from the Authorization header. Override in tests."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return decode_token(authorization.split(" ", 1)[1])
