"""Account-scoped settings for the signed-in user — currently a personal Gemini API key.

Gated to non-anonymous users (guests/demo can't store a key). The raw key is never returned;
GET exposes only whether a key is set and its last 4 chars for a masked hint.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import SessionDep, require_not_anonymous
from ..models import User, UserLLMKey
from ..services.secrets import encrypt_secret

router = APIRouter(prefix="/me", tags=["account"])

# Only real signed-in users (not anonymous guests) may store a key.
NotAnonUser = Annotated[User, Depends(require_not_anonymous)]


class LLMKeyStatus(BaseModel):
    has_key: bool
    gemini_last4: str | None = None


class LLMKeyUpdate(BaseModel):
    gemini_api_key: str


def _status(row: UserLLMKey | None) -> LLMKeyStatus:
    if row is None or not row.gemini_key_enc:
        return LLMKeyStatus(has_key=False)
    return LLMKeyStatus(has_key=True, gemini_last4=row.gemini_key_last4)


@router.get("/llm-key", response_model=LLMKeyStatus)
def get_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    return _status(session.get(UserLLMKey, user.uid))


@router.put("/llm-key", response_model=LLMKeyStatus)
def set_llm_key(payload: LLMKeyUpdate, user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    key = payload.gemini_api_key.strip()
    # Light validation — Google AI Studio keys start with "AIza" and are ~39 chars. We don't call
    # Google here (saves quota/latency); a bad key surfaces as a clear provider error on first use.
    if len(key) < 20 or " " in key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That doesn't look like a valid Gemini API key. It should be a single token "
            "starting with 'AIza'. Copy it again from Google AI Studio.",
        )
    row = session.get(UserLLMKey, user.uid)
    if row is None:
        row = UserLLMKey(user_uid=user.uid)
    row.gemini_key_enc = encrypt_secret(key)
    row.gemini_key_last4 = key[-4:]
    session.add(row)
    session.commit()
    session.refresh(row)
    return _status(row)


@router.delete("/llm-key", response_model=LLMKeyStatus)
def delete_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    row = session.get(UserLLMKey, user.uid)
    if row is not None:
        row.gemini_key_enc = None
        row.gemini_key_last4 = None
        session.add(row)
        session.commit()
    return LLMKeyStatus(has_key=False)
