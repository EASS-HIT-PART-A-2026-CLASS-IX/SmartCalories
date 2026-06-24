"""Account-scoped settings for the signed-in user — personal LLM API keys (Anthropic + Gemini).

Gated to non-anonymous users (guests/demo can't store keys). Raw keys are never returned;
GET exposes only whether each key is set plus its last 4 chars for a masked hint.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import SessionDep, require_not_anonymous
from ..models import User, UserLLMKey
from ..services.secrets import encrypt_secret

router = APIRouter(prefix="/me", tags=["account"])

# Only real signed-in users (not anonymous guests) may store keys.
NotAnonUser = Annotated[User, Depends(require_not_anonymous)]


class LLMKeyStatus(BaseModel):
    has_gemini: bool = False
    gemini_last4: str | None = None
    has_anthropic: bool = False
    anthropic_last4: str | None = None


class LLMKeyUpdate(BaseModel):
    """For each provider: a non-empty string sets the key, an empty string clears it, and a
    missing/None value leaves it unchanged."""

    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None


def _status(row: UserLLMKey | None) -> LLMKeyStatus:
    if row is None:
        return LLMKeyStatus()
    return LLMKeyStatus(
        has_gemini=bool(row.gemini_key_enc),
        gemini_last4=row.gemini_key_last4 if row.gemini_key_enc else None,
        has_anthropic=bool(row.anthropic_key_enc),
        anthropic_last4=row.anthropic_key_last4 if row.anthropic_key_enc else None,
    )


def _validate_gemini(key: str) -> None:
    # Google AI Studio keys are a single ~39-char token starting with "AIza".
    if " " in key or len(key) < 20 or not key.startswith("AIza"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That doesn't look like a Gemini API key. It should be a single token starting "
            "with 'AIza'. Copy it again from Google AI Studio.",
        )


def _validate_anthropic(key: str) -> None:
    # Anthropic keys are a single token starting with "sk-ant-".
    if " " in key or len(key) < 20 or not key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That doesn't look like an Anthropic API key. It should be a single token "
            "starting with 'sk-ant-'. Copy it again from the Anthropic Console.",
        )


@router.get("/llm-key", response_model=LLMKeyStatus)
def get_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    return _status(session.get(UserLLMKey, user.uid))


@router.put("/llm-key", response_model=LLMKeyStatus)
def set_llm_key(payload: LLMKeyUpdate, user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    # We don't call the providers here (saves quota/latency); a bad key surfaces as a clear
    # provider error on first use, and the per-message model label shows which one actually ran.
    row = session.get(UserLLMKey, user.uid) or UserLLMKey(user_uid=user.uid)

    if payload.gemini_api_key is not None:
        key = payload.gemini_api_key.strip()
        if key:
            _validate_gemini(key)
            row.gemini_key_enc = encrypt_secret(key)
            row.gemini_key_last4 = key[-4:]
        else:  # explicit empty string → clear
            row.gemini_key_enc = None
            row.gemini_key_last4 = None

    if payload.anthropic_api_key is not None:
        key = payload.anthropic_api_key.strip()
        if key:
            _validate_anthropic(key)
            row.anthropic_key_enc = encrypt_secret(key)
            row.anthropic_key_last4 = key[-4:]
        else:
            row.anthropic_key_enc = None
            row.anthropic_key_last4 = None

    session.add(row)
    session.commit()
    session.refresh(row)
    return _status(row)


@router.delete("/llm-key", response_model=LLMKeyStatus)
def delete_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    """Clear BOTH stored keys (back to the shared provider chain)."""
    row = session.get(UserLLMKey, user.uid)
    if row is not None:
        row.gemini_key_enc = None
        row.gemini_key_last4 = None
        row.anthropic_key_enc = None
        row.anthropic_key_last4 = None
        session.add(row)
        session.commit()
    return LLMKeyStatus()
