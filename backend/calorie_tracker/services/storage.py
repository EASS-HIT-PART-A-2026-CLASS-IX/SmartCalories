"""User-scoped file storage for uploaded images, generated reports, etc."""
from __future__ import annotations

import uuid
from pathlib import Path

from ..config import get_settings


def uploads_root() -> Path:
    return Path(get_settings().uploads_dir)


def user_dir(user_uid: str) -> Path:
    p = uploads_root() / user_uid
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_upload(user_uid: str, filename: str, content: bytes) -> Path:
    """Persist `content` under uploads/{uid}/{ulid}.{ext}; return the absolute path."""
    suffix = Path(filename).suffix or ".bin"
    if not suffix.startswith("."):
        suffix = "." + suffix
    safe_suffix = suffix.lower()
    if safe_suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf", ".csv", ".md"}:
        safe_suffix = ".bin"
    dest = user_dir(user_uid) / f"{uuid.uuid4().hex}{safe_suffix}"
    dest.write_bytes(content)
    return dest
