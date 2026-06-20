from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok", "app": get_settings().app_name}


@router.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe placeholder. Phase 12 expands to check Redis + DB."""
    return {"status": "ready"}
