from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import FoodEntry, UserGoals
from ..schemas import (
    MacrosSnapshot,
    StreakInfo,
    TDEERequest,
    TDEEResponse,
)
from ..services.nutrition import (
    aggregate,
    mifflin_st_jeor,
    streak_from_dates,
    suggest_macros,
    tdee,
)

router = APIRouter(prefix="/insights", tags=["insights"])


def _utc_today_bounds() -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today, today + timedelta(days=1)


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; coerce to UTC-aware so comparisons don't crash."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _snapshot_for(
    day_start: datetime, day_end: datetime, rows, goals: UserGoals | None
) -> MacrosSnapshot:
    bucket = [r for r in rows if day_start <= _ensure_aware(r.eaten_at) < day_end]
    totals = aggregate(bucket)
    return MacrosSnapshot(
        date=day_start.date().isoformat(),
        calories=int(totals["calories"]),
        protein_g=totals["protein_g"],
        carb_g=totals["carb_g"],
        fat_g=totals["fat_g"],
        target_kcal=goals.daily_kcal if goals else None,
        target_protein_g=goals.protein_g if goals else None,
        target_carb_g=goals.carb_g if goals else None,
        target_fat_g=goals.fat_g if goals else None,
    )


@router.get("/macros/today", response_model=MacrosSnapshot)
def macros_today(user: CurrentUser, session: SessionDep) -> MacrosSnapshot:
    start, end = _utc_today_bounds()
    rows = session.exec(
        select(FoodEntry)
        .where(FoodEntry.user_uid == user.uid)
        .where(FoodEntry.eaten_at >= start)
        .where(FoodEntry.eaten_at < end)
    ).all()
    goals = session.get(UserGoals, user.uid)
    return _snapshot_for(start, end, rows, goals)


@router.get("/macros/range", response_model=list[MacrosSnapshot])
def macros_range(
    user: CurrentUser,
    session: SessionDep,
    days: int = Query(default=7, ge=1, le=90),
) -> list[MacrosSnapshot]:
    today_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    range_start = today_end - timedelta(days=days)
    rows = session.exec(
        select(FoodEntry)
        .where(FoodEntry.user_uid == user.uid)
        .where(FoodEntry.eaten_at >= range_start)
        .where(FoodEntry.eaten_at < today_end)
    ).all()
    goals = session.get(UserGoals, user.uid)
    out: list[MacrosSnapshot] = []
    for offset in range(days):
        day_start = range_start + timedelta(days=offset)
        day_end = day_start + timedelta(days=1)
        out.append(_snapshot_for(day_start, day_end, rows, goals))
    return out


@router.get("/streak", response_model=StreakInfo)
def streak(user: CurrentUser, session: SessionDep) -> StreakInfo:
    rows = session.exec(
        select(FoodEntry.eaten_at).where(FoodEntry.user_uid == user.uid)
    ).all()
    eaten_dates: set = set()
    for r in rows:
        dt = r if isinstance(r, datetime) else r[0]
        eaten_dates.add(_ensure_aware(dt).date())
    return StreakInfo(days=streak_from_dates(eaten_dates))


@router.post("/tdee", response_model=TDEEResponse)
def compute_tdee_endpoint(payload: TDEERequest) -> TDEEResponse:
    bmr = mifflin_st_jeor(
        payload.weight_kg, payload.height_cm, payload.age_years, payload.sex
    )
    daily = tdee(bmr, payload.activity_level)
    macros = suggest_macros(daily, weight_kg=payload.weight_kg)
    return TDEEResponse(bmr=bmr, tdee=daily, suggested_macros=macros)
