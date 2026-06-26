from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Meal(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class Source(str, Enum):
    manual = "manual"
    photo = "photo"
    barcode = "barcode"
    voice = "voice"
    agent = "agent"


class User(SQLModel, table=True):
    __tablename__ = "user"

    uid: str = Field(primary_key=True, max_length=128, description="Firebase UID")
    email: str | None = None
    display_name: str | None = None
    is_anonymous: bool = False
    role: str = Field(default="user", description='"user" | "admin", mirrored from Firebase custom claim')
    timezone: str | None = None
    locale: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UserGoals(SQLModel, table=True):
    __tablename__ = "user_goals"

    user_uid: str = Field(foreign_key="user.uid", primary_key=True, max_length=128)
    daily_kcal: int | None = None
    protein_g: float | None = None
    carb_g: float | None = None
    fat_g: float | None = None
    tdee: int | None = None
    activity_level: str | None = None
    dietary_filters: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    weight_kg: float | None = None
    height_cm: float | None = None
    dob: datetime | None = None
    sex: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UserLLMKey(SQLModel, table=True):
    """User-supplied LLM provider API keys, encrypted at rest.

    One row per user holds an optional key for each supported provider (Anthropic, Gemini, Groq,
    OpenRouter) — the same providers the chat agent falls back through, in that order.
    `*_key_enc` holds a Fernet token (see services/secrets.py), never the raw key.
    `*_key_last4` is stored separately so the UI can show a masked hint without decrypting.
    """

    __tablename__ = "user_llm_key"

    user_uid: str = Field(foreign_key="user.uid", primary_key=True, max_length=128)
    anthropic_key_enc: str | None = Field(default=None, max_length=512)
    anthropic_key_last4: str | None = Field(default=None, max_length=8)
    gemini_key_enc: str | None = Field(default=None, max_length=512)
    gemini_key_last4: str | None = Field(default=None, max_length=8)
    groq_key_enc: str | None = Field(default=None, max_length=512)
    groq_key_last4: str | None = Field(default=None, max_length=8)
    openrouter_key_enc: str | None = Field(default=None, max_length=512)
    openrouter_key_last4: str | None = Field(default=None, max_length=8)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Preferences(SQLModel, table=True):
    __tablename__ = "preferences"

    user_uid: str = Field(foreign_key="user.uid", primary_key=True, max_length=128)
    theme: str = Field(default="system")
    language: str = Field(default="en")
    units: str = Field(default="metric")
    notifications: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class FoodEntry(SQLModel, table=True):
    __tablename__ = "food_entry"

    id: int | None = Field(default=None, primary_key=True)
    user_uid: str = Field(foreign_key="user.uid", index=True, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    calories: int = Field(ge=0, le=50_000)
    protein_g: float = Field(default=0.0, ge=0)
    carb_g: float = Field(default=0.0, ge=0)
    fat_g: float = Field(default=0.0, ge=0)
    serving_qty: float = Field(default=1.0, ge=0)
    serving_unit: str = Field(default="serving", max_length=40)
    meal: Meal = Field(default=Meal.snack)
    eaten_at: datetime = Field(default_factory=_now, index=True)
    source: Source = Field(default=Source.manual)
    image_path: str | None = None
    barcode: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class WaterLog(SQLModel, table=True):
    __tablename__ = "water_log"

    id: int | None = Field(default=None, primary_key=True)
    user_uid: str = Field(foreign_key="user.uid", index=True)
    ml: int = Field(ge=0, le=10_000)
    logged_at: datetime = Field(default_factory=_now, index=True)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"

    id: int | None = Field(default=None, primary_key=True)
    user_uid: str = Field(foreign_key="user.uid", index=True)
    title: str = Field(default="New chat", max_length=200)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_session.id", index=True)
    role: str = Field(default="user", max_length=16, description='"user" | "assistant" | "tool"')
    content: str = ""
    tool_calls: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    image_path: str | None = None
    # LLM model id that produced this message (assistant only), e.g. "gemini/gemini-2.0-flash"
    # or "anthropic/claude-3-5-haiku-latest". Null for user messages and older rows.
    model: str | None = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=_now)


