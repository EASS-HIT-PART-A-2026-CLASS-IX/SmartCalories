"""Dev-only auth-helper endpoint: `/auth/demo`."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..config import get_settings
from ..deps import SessionDep
from ..services.demo_seed import DEMO_UID, populate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/demo")
def start_demo(session: SessionDep) -> dict:
    """Refreshes the rich demo dataset for `demo-uid` and returns the literal `demo-token`
    that the backend's dev escape hatch accepts. Disabled outside `ENVIRONMENT=dev`."""
    settings = get_settings()
    if settings.environment != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is only available in development",
        )
    counts = populate(session)
    return {
        "uid": DEMO_UID,
        "token": "demo-token",
        "email": "demo@smartcalories.local",
        "display_name": "Alex Demo",
        "is_anonymous": False,
        "seeded": counts,
    }
