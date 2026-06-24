"""smolagents-based chat agent for SmartCalories.

The chat agent is a smolagents `ToolCallingAgent` (sequential JSON tool calls — NOT a
code-executing `CodeAgent`, since our tools mutate the user's diary). Tools are built
per-request so each one closes over the request's DB session + user (see `tools.py`).

Models are driven through LiteLLM. To keep the free-tier resilience the project relied on,
`_FallbackModel` wraps the Gemini → Groq → OpenRouter → Ollama chain and advances to the next
provider on any error (rate-limit / 503 / timeout).

Note: the photo-analysis agent in `vision.py` is a separate pydantic-ai structured-output
agent and is intentionally NOT migrated — the chat agent reaches it via `analyze_image_tool`.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from smolagents import LiteLLMModel, ToolCallingAgent, WebSearchTool
from smolagents.models import ChatMessage, Model
from smolagents.monitoring import LogLevel
from sqlmodel import Session

from ..config import get_settings
from ..models import User
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# litellm model-id prefixes per provider. Defaults mirror the previous pydantic-ai chains.
# Anthropic (Claude) is paid — no free tier — but when ANTHROPIC_API_KEY is set it's tried first.
# Current model ids (cheap → capable). Override via ANTHROPIC_FALLBACK_MODELS if your account
# exposes different ids. (The older claude-3-5-*-latest aliases now 404 for new accounts.)
_DEFAULT_ANTHROPIC_CHAIN = (
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
)
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
_DEFAULT_OPENROUTER_CHAIN = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-2-9b-it:free",
)

# Per-request timeout (seconds) passed to each LiteLLM call. Bounds how long a stalled provider
# can block before `_FallbackModel` advances to the next one.
_REQUEST_TIMEOUT_S = 30


def _lite(model_id: str, **kwargs) -> "LiteLLMModel":
    # retry=False: don't let smolagents back off + retry rate-limit errors per-model — that would
    #   compound across the whole chain into a long hang. Instead a 429 raises immediately and
    #   _FallbackModel advances to the next provider. num_retries=0 disables LiteLLM's own retries.
    return LiteLLMModel(
        model_id=model_id, timeout=_REQUEST_TIMEOUT_S, num_retries=0, retry=False, **kwargs
    )


class _FallbackModel(Model):
    """Try each wrapped model in order; advance to the next on any generation error."""

    def __init__(self, models: list[Model]):
        super().__init__()
        if not models:
            raise ValueError("_FallbackModel requires at least one model")
        self._models = models
        self.model_id = getattr(models[0], "model_id", "fallback")
        # The model id that produced the most recent successful generation (for attribution).
        self.last_used_model_id: str | None = None

    def generate(self, messages, **kwargs) -> ChatMessage:  # type: ignore[override]
        last_exc: Exception | None = None
        for m in self._models:
            try:
                result = m.generate(messages, **kwargs)
                self.last_used_model_id = getattr(m, "model_id", None)
                return result
            except Exception as exc:  # noqa: BLE001 — any provider failure → try the next
                last_exc = exc
                # Truncate: provider errors (esp. 429 quota JSON) are huge and spam logs.
                summary = " ".join(str(exc).split())[:160]
                logger.warning("model %s failed, falling back: %s", getattr(m, "model_id", m), summary)
        assert last_exc is not None
        raise last_exc


def used_model_id(model) -> str | None:
    """The model id that produced the most recent response, for per-message attribution.

    For a `_FallbackModel` this is the provider that actually answered (set on each successful
    generate); for a single model it's its fixed `model_id`.
    """
    return getattr(model, "last_used_model_id", None) or getattr(model, "model_id", None)


def _build_model_chain() -> list[Model]:
    settings = get_settings()
    models: list[Model] = []

    # Claude first when configured (paid; preferred quality), then the free-tier providers.
    if settings.anthropic_api_key:
        chain = settings.anthropic_fallback_models or list(_DEFAULT_ANTHROPIC_CHAIN)
        models += [
            _lite(f"anthropic/{name}", api_key=settings.anthropic_api_key) for name in chain
        ]
    if settings.gemini_api_key:
        chain = settings.gemini_fallback_models or list(_DEFAULT_GEMINI_CHAIN)
        models += [_lite(f"gemini/{name}", api_key=settings.gemini_api_key) for name in chain]
    if settings.groq_api_key:
        chain = settings.groq_fallback_models or list(_DEFAULT_GROQ_CHAIN)
        models += [_lite(f"groq/{name}", api_key=settings.groq_api_key) for name in chain]
    if settings.openrouter_api_key:
        chain = settings.openrouter_fallback_models or list(_DEFAULT_OPENROUTER_CHAIN)
        models += [
            _lite(f"openrouter/{name}", api_key=settings.openrouter_api_key) for name in chain
        ]
    if settings.ollama_base_url:
        models.append(
            _lite(
                f"ollama_chat/{settings.ollama_model}",
                api_base=settings.ollama_base_url.rstrip("/"),
                api_key="ollama-local",
            )
        )
    return models


@lru_cache(maxsize=1)
def get_default_model() -> Model:
    """Resolve the configured model chain into a single (possibly fallback) Model.

    Cached so we don't rebuild LiteLLM clients on every request. Tests monkeypatch this.
    """
    models = _build_model_chain()
    if not models:
        raise RuntimeError(
            "No LLM provider configured. Set ANTHROPIC_API_KEY / GEMINI_API_KEY / "
            "GROQ_API_KEY / OPENROUTER_API_KEY / OLLAMA_BASE_URL."
        )
    return models[0] if len(models) == 1 else _FallbackModel(models)


def get_title_model() -> Model:
    """Model used for the cheap session-title call. Defaults to the shared chain (so it never
    spends a user's personal quota on titles). Separate hook so tests can stub it independently."""
    return get_default_model()


def _clean_title(raw: str) -> str:
    """First line, strip surrounding quotes + trailing punctuation, cap length."""
    line = (raw or "").strip().splitlines()[0].strip() if (raw or "").strip() else ""
    line = line.strip("\"'“”").strip().rstrip(".!?,:;").strip()
    return line[:60]


def generate_session_title(first_user: str, first_assistant: str = "") -> str | None:
    """One lightweight LLM call → a short, human-friendly chat title. Best-effort: returns None
    on any failure (caller keeps the fallback truncation title)."""
    from smolagents.models import ChatMessage, MessageRole

    prompt = (
        "Write a concise 3–6 word title (Title Case, no quotes, no ending punctuation) that "
        "summarizes what this chat is about. Reply with ONLY the title.\n\n"
        f"User: {first_user.strip()[:500]}\n"
    )
    if first_assistant:
        prompt += f"Assistant: {first_assistant.strip()[:500]}\n"
    try:
        resp = get_title_model().generate([ChatMessage(role=MessageRole.USER, content=prompt)])
    except Exception:  # noqa: BLE001 — titling is best-effort, never fail the turn
        logger.warning("session title generation failed", exc_info=True)
        return None
    title = _clean_title(resp.content or "")
    return title or None


def _model_for_user(user_gemini_key: str | None) -> Model:
    """When the user supplied their own Gemini key, try THEIR Gemini models first (their quota),
    then fall through to the shared free-tier chain. Otherwise use the shared chain as-is."""
    if not user_gemini_key:
        return get_default_model()
    chain = get_settings().gemini_fallback_models or list(_DEFAULT_GEMINI_CHAIN)
    user_models: list[Model] = [
        _lite(f"gemini/{name}", api_key=user_gemini_key) for name in chain
    ]
    try:
        shared = get_default_model()
    except RuntimeError:
        shared = None
    if shared is not None:
        # `shared` may itself be a _FallbackModel; nesting is fine since generate() just delegates.
        return _FallbackModel([*user_models, shared])
    return _FallbackModel(user_models) if len(user_models) > 1 else user_models[0]


def build_agent(
    session: Session,
    user: User,
    *,
    model: Model | None = None,
    user_gemini_key: str | None = None,
) -> ToolCallingAgent:
    """Construct a per-request chat agent whose tools close over this session + user.

    If `model` is given it's used verbatim (tests inject a scripted model). Otherwise, when the
    user supplied their own Gemini key it's preferred; else the shared provider chain is used.
    """
    # Imported here (not at module top) to avoid a circular import: tools.py imports nothing
    # from this module's request path, but keeping the import local mirrors the old layout.
    from .tools import build_request_tools

    tools = [*build_request_tools(session, user), WebSearchTool()]
    return ToolCallingAgent(
        tools=tools,
        model=model or _model_for_user(user_gemini_key),
        instructions=SYSTEM_PROMPT,
        max_steps=8,
        verbosity_level=LogLevel.ERROR,
    )
