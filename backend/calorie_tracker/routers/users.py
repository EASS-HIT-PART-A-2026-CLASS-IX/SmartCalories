from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..deps import CurrentUser, SessionDep
from ..models import Preferences, UserGoals
from ..schemas import (
    GoalsRead,
    GoalsUpsert,
    PreferencesRead,
    PreferencesUpsert,
    UserPatch,
    UserRead,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user.model_dump())


@router.patch("/me", response_model=UserRead)
def update_me(payload: UserPatch, user: CurrentUser, session: SessionDep) -> UserRead:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.model_validate(user.model_dump())


@router.get("/me/goals", response_model=GoalsRead)
def read_goals(user: CurrentUser, session: SessionDep) -> GoalsRead:
    goals = session.get(UserGoals, user.uid)
    if goals is None:
        return GoalsRead()
    return GoalsRead.model_validate(goals.model_dump())


@router.put("/me/goals", response_model=GoalsRead)
def upsert_goals(payload: GoalsUpsert, user: CurrentUser, session: SessionDep) -> GoalsRead:
    goals = session.get(UserGoals, user.uid)
    data = payload.model_dump()
    if goals is None:
        goals = UserGoals(user_uid=user.uid, **data)
    else:
        for field, value in data.items():
            setattr(goals, field, value)
        goals.updated_at = datetime.now(timezone.utc)
    session.add(goals)
    session.commit()
    session.refresh(goals)
    return GoalsRead.model_validate(goals.model_dump())


@router.get("/me/preferences", response_model=PreferencesRead)
def read_preferences(user: CurrentUser, session: SessionDep) -> PreferencesRead:
    prefs = session.get(Preferences, user.uid)
    if prefs is None:
        return PreferencesRead()
    return PreferencesRead.model_validate(prefs.model_dump())


@router.put("/me/preferences", response_model=PreferencesRead)
def upsert_preferences(
    payload: PreferencesUpsert, user: CurrentUser, session: SessionDep
) -> PreferencesRead:
    prefs = session.get(Preferences, user.uid)
    data = payload.model_dump()
    if prefs is None:
        prefs = Preferences(user_uid=user.uid, **data)
    else:
        for field, value in data.items():
            setattr(prefs, field, value)
        prefs.updated_at = datetime.now(timezone.utc)
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return PreferencesRead.model_validate(prefs.model_dump())
