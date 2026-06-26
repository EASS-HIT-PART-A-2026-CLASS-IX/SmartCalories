from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartCalories"
    environment: str = Field(default="dev", description="dev | test | prod")

    secret_key: str | None = Field(
        default=None,
        description="App secret used to derive the Fernet key that encrypts user-supplied API "
        "keys at rest. MUST be set in prod; dev falls back to an insecure constant.",
    )

    database_url: str = Field(
        default="sqlite:///./data/dev.db",
        description="Postgres URL for Neon in prod, sqlite for local dev fallback.",
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def _force_psycopg3(cls, value: str) -> str:
        """SQLAlchemy's default 'postgresql://' scheme imports psycopg2; we ship psycopg 3.

        Rewrite bare 'postgresql://' (and 'postgres://') to 'postgresql+psycopg://' so users
        can paste a vanilla Neon URL without knowing the SQLAlchemy URL convention.
        """
        if value.startswith("postgresql+"):
            return value
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        return value

    redis_url: str = Field(default="redis://localhost:6379/0")

    firebase_project_id: str | None = None
    firebase_credentials_path: str | None = Field(
        default=None,
        description="Path to a Firebase Admin service-account JSON. Skipped in tests.",
    )
    firebase_credentials_json: str | None = Field(
        default=None,
        description="Firebase Admin service-account JSON as a string (alternative to a file path). Takes precedence over firebase_credentials_path.",
    )

    # Anthropic (Claude) — paid (no free tier). When set, Claude is tried FIRST in the chat
    # chain, ahead of the free-tier providers below. Get a key at https://console.anthropic.com.
    anthropic_api_key: str | None = None
    anthropic_fallback_models: list[str] | None = Field(
        default=None,
        description="Comma-separated Anthropic model names tried in order (e.g. claude-3-5-haiku-latest). Defaults to a haiku→sonnet pair.",
    )

    gemini_api_key: str | None = None
    gemini_fallback_models: list[str] | None = Field(
        default=None,
        description="Comma-separated Gemini model names tried in order; FallbackModel falls through on rate-limit/503/etc.",
    )

    # Free LLM fallbacks tried after Gemini exhausts its chain.
    # Groq has a generous free tier (Llama 3.3 70B + Gemma 2). Get a key at https://console.groq.com.
    groq_api_key: str | None = None
    groq_fallback_models: list[str] | None = Field(
        default=None,
        description="Comma-separated Groq model names. Defaults to llama-3.3-70b-versatile, gemma2-9b-it.",
    )

    # OpenRouter exposes free hosted Llama/Gemma/Mistral with a `:free` suffix. Sign up at
    # https://openrouter.ai. These run with strict daily caps but cost nothing.
    openrouter_api_key: str | None = None
    openrouter_fallback_models: list[str] | None = Field(
        default=None,
        description="Comma-separated OpenRouter model names. Defaults to a couple of `:free` Llama/Gemma builds.",
    )

    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    uploads_dir: str = "uploads"

    rate_limit_per_min: int = 120

    stream_token_delay_ms: int = Field(
        default=55,
        description="Per-word delay (ms) on streamed agent responses. 30-70 feels like ChatGPT; 0 disables pacing.",
    )
    stream_thinking_delay_ms: int = Field(
        default=400, description="Pause between 'thinking' and the first token, gives the spinner time to register."
    )
    stream_tool_delay_ms: int = Field(
        default=250, description="Pause around tool_call/tool_result events so the chips animate visibly."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
