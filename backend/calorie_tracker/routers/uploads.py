"""Serve files saved by `services.storage.save_upload` back to their owner.

Path layout: ``uploads/{user_uid}/{filename}``. Only the user that owns the directory may
read the file. Authenticates via the standard ``Authorization`` header OR an explicit
``?token=`` query param so HTML ``<img>`` tags (which can't send auth headers) can render
images. The token is the same Firebase ID token / API key / dev `demo-token` used elsewhere.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse

from ..auth import verify_firebase_token
from ..services.storage import uploads_root

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _resolve_uid(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    token: Annotated[str | None, Query()] = None,
) -> str:
    """Accept either Bearer header or `?token=...` and return the uid."""
    auth_value = authorization
    if not auth_value and token:
        auth_value = f"Bearer {token}"
    decoded = verify_firebase_token(auth_value)
    return decoded["uid"]


def _safe_path(user_uid: str, rest: str) -> Path:
    root = uploads_root().resolve()
    candidate = (root / user_uid / rest).resolve()
    if not str(candidate).startswith(str(root / user_uid)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    return candidate


@router.get("/{user_uid}/{rest:path}")
def get_file(
    user_uid: str,
    rest: str,
    uid: Annotated[str, Depends(_resolve_uid)],
):
    if user_uid != uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    path = _safe_path(user_uid, rest)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(path)
