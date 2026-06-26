"""Account-scoped settings for the signed-in user — personal LLM API keys.

A user may store a key for any of the chat agent's fallback providers (Anthropic, Gemini, Groq,
OpenRouter); the agent then uses their keys first, in that same fallback order, before the shared
quota. Gated to non-anonymous users (guests/demo can't store keys). Raw keys are never returned;
GET exposes only whether each key is set plus its last 4 chars for a masked hint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import SessionDep, require_not_anonymous
from ..models import User, UserLLMKey
from ..services.secrets import encrypt_secret

router = APIRouter(prefix="/me", tags=["account"])

# Only real signed-in users (not anonymous guests) may store keys.
NotAnonUser = Annotated[User, Depends(require_not_anonymous)]


@dataclass(frozen=True)
class _ProviderSpec:
    """Drives validation + (de)serialisation for one provider.

    `name` is the stem shared across the model columns (`{name}_key_enc` / `{name}_key_last4`),
    the request payload field (`{name}_api_key`), and the status fields (`has_{name}` /
    `{name}_last4`). `prefix` is the expected key prefix used for a cheap client-side-style check.
    """

    name: str
    label: str
    prefix: str
    min_len: int = 20


# Order mirrors the agent's fallback chain (anthropic → gemini → groq → openrouter).
_PROVIDERS: tuple[_ProviderSpec, ...] = (
    _ProviderSpec("anthropic", "Anthropic", "sk-ant-"),
    _ProviderSpec("gemini", "Gemini", "AIza"),
    _ProviderSpec("groq", "Groq", "gsk_"),
    _ProviderSpec("openrouter", "OpenRouter", "sk-or-"),
)


class LLMKeyStatus(BaseModel):
    has_anthropic: bool = False
    anthropic_last4: str | None = None
    has_gemini: bool = False
    gemini_last4: str | None = None
    has_groq: bool = False
    groq_last4: str | None = None
    has_openrouter: bool = False
    openrouter_last4: str | None = None


class LLMKeyUpdate(BaseModel):
    """For each provider: a non-empty string sets the key, an empty string clears it, and a
    missing/None value leaves it unchanged."""

    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None


def _status(row: UserLLMKey | None) -> LLMKeyStatus:
    out = LLMKeyStatus()
    if row is None:
        return out
    for p in _PROVIDERS:
        enc = getattr(row, f"{p.name}_key_enc")
        setattr(out, f"has_{p.name}", bool(enc))
        setattr(out, f"{p.name}_last4", getattr(row, f"{p.name}_key_last4") if enc else None)
    return out


def _validate(p: _ProviderSpec, key: str) -> None:
    # Cheap shape check only — we don't call the provider here (saves quota/latency). A truly bad
    # key surfaces as a clear provider error on first use, and the per-message model label shows
    # which provider actually answered.
    if " " in key or len(key) < p.min_len or not key.startswith(p.prefix):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"That doesn't look like a {p.label} API key. It should be a single token "
                f"starting with '{p.prefix}'. Copy it again from the {p.label} console."
            ),
        )


@router.get("/llm-key", response_model=LLMKeyStatus)
def get_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    return _status(session.get(UserLLMKey, user.uid))


@router.put("/llm-key", response_model=LLMKeyStatus)
def set_llm_key(payload: LLMKeyUpdate, user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    row = session.get(UserLLMKey, user.uid) or UserLLMKey(user_uid=user.uid)

    for p in _PROVIDERS:
        value = getattr(payload, f"{p.name}_api_key")
        if value is None:  # unchanged
            continue
        key = value.strip()
        if key:
            _validate(p, key)
            setattr(row, f"{p.name}_key_enc", encrypt_secret(key))
            setattr(row, f"{p.name}_key_last4", key[-4:])
        else:  # explicit empty string → clear
            setattr(row, f"{p.name}_key_enc", None)
            setattr(row, f"{p.name}_key_last4", None)

    session.add(row)
    session.commit()
    session.refresh(row)
    return _status(row)


@router.delete("/llm-key", response_model=LLMKeyStatus)
def delete_llm_key(user: NotAnonUser, session: SessionDep) -> LLMKeyStatus:
    """Clear ALL stored keys (back to the shared provider chain)."""
    row = session.get(UserLLMKey, user.uid)
    if row is not None:
        for p in _PROVIDERS:
            setattr(row, f"{p.name}_key_enc", None)
            setattr(row, f"{p.name}_key_last4", None)
        session.add(row)
        session.commit()
    return LLMKeyStatus()
