from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import FoodEntry, Meal, Source
from ..schemas import DiaryEntryPatch, DiaryEntryRead, FoodEntryCreate

router = APIRouter(prefix="/diary", tags=["diary"])


def _meal_from_str(value: str) -> Meal:
    try:
        return Meal(value.strip().lower())
    except ValueError:
        return Meal.snack


@router.get("", response_model=list[DiaryEntryRead])
def list_entries(
    user: CurrentUser,
    session: SessionDep,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> list[DiaryEntryRead]:
    stmt = select(FoodEntry).where(FoodEntry.user_uid == user.uid)
    if from_ is not None:
        stmt = stmt.where(FoodEntry.eaten_at >= from_)
    if to is not None:
        stmt = stmt.where(FoodEntry.eaten_at <= to)
    rows = session.exec(stmt.order_by(FoodEntry.eaten_at.desc())).all()
    return [DiaryEntryRead.from_orm_row(r) for r in rows]


@router.get("/today", response_model=list[DiaryEntryRead])
def list_today(user: CurrentUser, session: SessionDep) -> list[DiaryEntryRead]:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    rows = session.exec(
        select(FoodEntry)
        .where(FoodEntry.user_uid == user.uid)
        .where(FoodEntry.eaten_at >= today)
        .where(FoodEntry.eaten_at < tomorrow)
        .order_by(FoodEntry.eaten_at)
    ).all()
    return [DiaryEntryRead.from_orm_row(r) for r in rows]


@router.post("", response_model=DiaryEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: FoodEntryCreate, user: CurrentUser, session: SessionDep
) -> DiaryEntryRead:
    entry = FoodEntry(
        user_uid=user.uid,
        name=payload.name,
        calories=payload.calories,
        meal=_meal_from_str(payload.meal),
        protein_g=payload.protein_g,
        carb_g=payload.carb_g,
        fat_g=payload.fat_g,
        serving_qty=payload.serving_qty,
        serving_unit=payload.serving_unit,
        eaten_at=payload.eaten_at or datetime.now(timezone.utc),
        source=payload.source or Source.manual,
        notes=payload.notes,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return DiaryEntryRead.from_orm_row(entry)


def _owned(entry_id: int, user_uid: str, session) -> FoodEntry:
    entry = session.get(FoodEntry, entry_id)
    if entry is None or entry.user_uid != user_uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


@router.patch("/{entry_id}", response_model=DiaryEntryRead)
def patch_entry(
    entry_id: int, payload: DiaryEntryPatch, user: CurrentUser, session: SessionDep
) -> DiaryEntryRead:
    entry = _owned(entry_id, user.uid, session)
    data = payload.model_dump(exclude_unset=True)
    if "meal" in data and data["meal"] is not None:
        data["meal"] = _meal_from_str(data["meal"])
    for field, value in data.items():
        setattr(entry, field, value)
    entry.updated_at = datetime.now(timezone.utc)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return DiaryEntryRead.from_orm_row(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, user: CurrentUser, session: SessionDep) -> Response:
    entry = _owned(entry_id, user.uid, session)
    session.delete(entry)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
