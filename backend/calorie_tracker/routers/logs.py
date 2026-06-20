from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import WaterLog
from ..schemas import LogRangeRead, WaterLogCreate

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/water", status_code=status.HTTP_201_CREATED)
def log_water(payload: WaterLogCreate, user: CurrentUser, session: SessionDep) -> dict:
    row = WaterLog(user_uid=user.uid, ml=payload.ml)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id, "ml": row.ml, "logged_at": row.logged_at.isoformat()}


@router.get("/range", response_model=LogRangeRead)
def range_summary(
    user: CurrentUser,
    session: SessionDep,
    days: int = Query(default=7, ge=1, le=90),
) -> LogRangeRead:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    waters = session.exec(
        select(WaterLog).where(WaterLog.user_uid == user.uid).where(WaterLog.logged_at >= since)
    ).all()
    return LogRangeRead(water_ml_total=sum(w.ml for w in waters))
