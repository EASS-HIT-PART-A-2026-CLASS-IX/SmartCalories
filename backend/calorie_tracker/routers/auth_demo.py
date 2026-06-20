"""Dev-only auth-helper endpoints: `/auth/demo` and `/auth/playground`."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..config import get_settings
from ..deps import CurrentUser, SessionDep
from ..services.demo_seed import DEMO_UID, populate, populate_starter

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


@router.post("/playground")
def seed_playground(user: CurrentUser, session: SessionDep) -> dict:
    """Seed lightweight starter data for the current user. Idempotent — skips if the user
    already has any diary entries. Used by the frontend's "Continue as guest" flow."""
    counts = populate_starter(session, user.uid)
    return {"uid": user.uid, "seeded": counts}
