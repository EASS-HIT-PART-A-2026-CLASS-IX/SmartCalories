from __future__ import annotations

from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from .auth import verify_firebase_token
from .db import get_session
from .models import User

SessionDep = Annotated[Session, Depends(get_session)]
DecodedTokenDep = Annotated[dict[str, Any], Depends(verify_firebase_token)]


def get_current_user(decoded: DecodedTokenDep, session: SessionDep) -> User:
    """Resolve the authenticated user, auto-creating their row on first sight."""
    uid: str | None = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing uid")

    user = session.get(User, uid)
    is_anonymous = (
        decoded.get("firebase", {}).get("sign_in_provider") == "anonymous"
        if isinstance(decoded.get("firebase"), dict)
        else bool(decoded.get("is_anonymous", False))
    )
    desired_role = decoded.get("role") or "user"

    if user is None:
        user = User(
            uid=uid,
            email=decoded.get("email"),
            display_name=decoded.get("name") or decoded.get("display_name"),
            is_anonymous=is_anonymous,
            role=desired_role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    changed = False
    if user.role != desired_role:
        user.role = desired_role
        changed = True
    if user.is_anonymous != is_anonymous:
        user.is_anonymous = is_anonymous
        changed = True
    if changed:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: str) -> Callable[[User], User]:
    def _check(user: CurrentUser) -> User:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires {role} role")
        return user

    return _check


def require_not_anonymous(user: CurrentUser) -> User:
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Save your progress (sign in) to use this feature",
        )
    return user
