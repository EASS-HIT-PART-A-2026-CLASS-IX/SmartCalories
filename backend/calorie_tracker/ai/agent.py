"""Pydantic AI agent for SmartCalories.

If `GEMINI_API_KEY` is set we use Gemini 2.5 Flash; otherwise we fall back to a
non-tool-calling TestModel so the package can be imported and exercised without
contacting any LLM. Tests explicitly override the model via `agent.override()`.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel
from sqlmodel import Session

from ..config import get_settings
from ..models import User
from ..services.cache import AsyncCache
from .prompts import SYSTEM_PROMPT


@dataclass
class AgentDeps:
    """Dependencies injected into every tool call. Built per request.

    `db_lock` serializes tools that mutate the SQLModel session: Pydantic AI dispatches
    tool calls concurrently, but a SQLAlchemy `Session` is not safe for parallel
    `commit()`s. Each writing tool wraps its body in `with ctx.deps.db_lock:`.
    """

    session: Session
    user: User
    cache: AsyncCache
    request_id: str = "local"
    db_lock: threading.RLock = field(default_factory=threading.RLock)


_DEFAULT_GEMINI_CHAIN = (
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
)

_DEFAULT_GROQ_CHAIN = (
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
)

# Note: OpenRouter `:free` model availability rotates — these are stable as of 2026-05.
# Users can override with OPENROUTER_FALLBACK_MODELS env var.
_DEFAULT_OPENROUTER_CHAIN = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-2-9b-it:free",
)


def _gemini_models(api_key: str, chain: list[str]) -> list[Model]:
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=api_key)
    return [GoogleModel(name, provider=provider) for name in chain]


def _groq_models(api_key: str, chain: list[str]) -> list[Model]:
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    provider = GroqProvider(api_key=api_key)
    return [GroqModel(name, provider=provider) for name in chain]


def _openrouter_models(api_key: str, chain: list[str]) -> list[Model]:
    """OpenRouter speaks the OpenAI Chat Completions wire format, so we point Pydantic AI's
    OpenAIChatModel at https://openrouter.ai/api/v1 with the OpenRouter API key."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    return [OpenAIChatModel(name, provider=provider) for name in chain]


def _ollama_model(base_url: str, model_name: str) -> Model:
    """Ollama exposes an OpenAI-compatible Chat Completions endpoint at /v1, so we reuse the
    OpenAI provider with a dummy api_key (Ollama ignores it but Pydantic AI requires a string).
    Gemma 4 has native tool calling + vision so it works as a real fallback, not just for text.
    """
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(api_key="ollama-local", base_url=base_url.rstrip("/"))
    return OpenAIChatModel(model_name, provider=provider)


def _build_default_model() -> Model:
    """Free-tier LLM chain. Tries Gemini → Groq → OpenRouter → local Ollama in order.

    Pydantic AI's `FallbackModel` retries the next model on rate-limit/503/timeout errors,
    so when every cloud free tier is exhausted we fall through to whatever Ollama is serving
    locally (Gemma 4 by default — native tool calling and vision). All four are genuinely free.

    A provider is only included if its corresponding env var is set. Override each provider's
    chain via `*_FALLBACK_MODELS` env vars (comma-separated).
    """
    settings = get_settings()
    models: list[Model] = []

    if settings.gemini_api_key:
        models.extend(
            _gemini_models(
                settings.gemini_api_key,
                settings.gemini_fallback_models or list(_DEFAULT_GEMINI_CHAIN),
            )
        )

    if settings.groq_api_key:
        models.extend(
            _groq_models(
                settings.groq_api_key,
                settings.groq_fallback_models or list(_DEFAULT_GROQ_CHAIN),
            )
        )

    if settings.openrouter_api_key:
        models.extend(
            _openrouter_models(
                settings.openrouter_api_key,
                settings.openrouter_fallback_models or list(_DEFAULT_OPENROUTER_CHAIN),
            )
        )

    if settings.ollama_base_url:
        models.append(_ollama_model(settings.ollama_base_url, settings.ollama_model))

    if not models:
        return TestModel(
            call_tools=[],
            custom_output_text=(
                "(Set GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY / OLLAMA_BASE_URL to enable real responses.)"
            ),
        )

    if len(models) == 1:
        return models[0]

    from pydantic_ai.models.fallback import FallbackModel

    return FallbackModel(*models)


agent: Agent[AgentDeps, str] = Agent(
    _build_default_model(),
    deps_type=AgentDeps,
    output_type=str,
    system_prompt=SYSTEM_PROMPT,
    retries=3,
)


# Tools live in `tools.py` and self-register on import.
from . import tools  # noqa: E402,F401
