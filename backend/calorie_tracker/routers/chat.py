from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlmodel import Session, select

from ..ai.agent import build_agent, generate_session_title, used_model_id
from ..auth import decode_token
from ..deps import CurrentUser, SessionDep, get_current_user
from ..models import ChatMessage, ChatSession, User, UserLLMKey
from ..services.secrets import decrypt_secret

logger = logging.getLogger(__name__)


def _user_gemini_key(session: Session, user: User) -> str | None:
    """The signed-in user's own Gemini key (decrypted), or None. Guests never have one."""
    if user.is_anonymous:
        return None
    row = session.get(UserLLMKey, user.uid)
    if row is None or not row.gemini_key_enc:
        return None
    return decrypt_secret(row.gemini_key_enc)


def _friendly_provider_error(exc: Exception, *, has_own_key: bool, is_anonymous: bool) -> str:
    """Map a raw LLM/provider exception to a clear, user-facing sentence."""
    text = " ".join(str(exc).split()).lower()
    name = type(exc).__name__.lower()

    def _own_key_hint() -> str:
        if has_own_key:
            return " Your personal key is also at its limit — please wait a moment and retry."
        if is_anonymous:
            return " Sign in and add your own free Gemini API key (in Settings) to skip the shared limits."
        return " Tip: add your own free Gemini API key in Settings to skip the shared limits."

    is_auth = any(
        k in text
        for k in [
            "api key not valid",
            "invalid api key",
            "invalid authentication",
            "api_key",
            "unauthenticated",
            "permission denied",
            "401",
            "403",
        ]
    )
    is_rate = (
        "ratelimit" in name
        or any(
            k in text
            for k in ["rate limit", "rate_limit", "429", "quota", "resource_exhausted", "exceeded"]
        )
    )
    is_overloaded = any(
        k in text
        for k in ["overloaded", "503", "529", "service unavailable", "temporarily unavailable"]
    )
    is_timeout = any(k in text for k in ["timeout", "timed out", "deadline exceeded"])

    if is_auth and has_own_key:
        return (
            "Your Gemini API key was rejected by Google. Open Settings to re-enter a valid key "
            "(or remove it to fall back to the shared models)."
        )
    if is_rate:
        return (
            "The AI is rate-limited right now — the free model quota is temporarily used up."
            + _own_key_hint()
        )
    if is_overloaded:
        return (
            "The AI model is temporarily overloaded on the provider's side. "
            "Give it a few seconds and try again." + _own_key_hint()
        )
    if is_timeout:
        return "The AI took too long to respond. Please try again."
    if is_auth:
        return "The AI provider rejected the request (authentication problem). Please try again later."
    return "The AI provider had a problem handling that. Please try again in a moment."


async def _run_agent_or_raise(
    agent, task: str, *, has_own_key: bool, is_anonymous: bool
) -> str:
    """Run the agent off the event loop; on any provider/LLM failure raise a 503 HTTPException
    carrying a clear, user-facing message (the frontend shows it inline + as a toast)."""
    try:
        return await run_in_threadpool(lambda: str(agent.run(task)))
    except Exception as exc:  # noqa: BLE001 — classify + surface, never a raw 500
        logger.exception("agent run failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_friendly_provider_error(
                exc, has_own_key=has_own_key, is_anonymous=is_anonymous
            ),
        ) from exc

# How many prior turns to replay into the agent task for conversational continuity.
_HISTORY_TURNS = 12


def _build_task(session: Session, session_id: int, content: str, image_path: str | None) -> str:
    """Compose the smolagents task: a short prior-turn transcript + the current user message.

    smolagents agents are rebuilt per-request (their tools close over this request's session),
    so memory isn't carried across calls — we inline recent history into the task instead.
    Image bytes are never replayed; if the current message has a photo we point the agent at
    `analyze_image_tool` with the path.
    """
    rows = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.role.in_(("user", "assistant")))  # type: ignore[attr-defined]
        .order_by(ChatMessage.id)
    ).all()
    # Drop the just-persisted current user message (last row) before building the transcript.
    prior = [r for r in rows if r.content][:-1] if rows else []
    prior = prior[-_HISTORY_TURNS:]

    parts: list[str] = []
    if prior:
        transcript = "\n".join(
            f"{'User' if r.role == 'user' else 'Assistant'}: {r.content}" for r in prior
        )
        parts.append("Conversation so far:\n" + transcript)
    parts.append(f"User: {content}")
    if image_path:
        parts.append(
            f"[The user attached a photo at image_path='{image_path}'. Call analyze_image_tool "
            "with this exact path to analyze it before answering.]"
        )
    return "\n\n".join(parts)


router = APIRouter(prefix="/chat", tags=["chat"])


class SessionCreate(BaseModel):
    title: str = "New chat"


class SessionRead(BaseModel):
    id: int
    title: str
    created_at: datetime


class MessagePayload(BaseModel):
    content: str
    image_path: str | None = None


class MessageRead(BaseModel):
    id: int
    role: str
    content: str
    image_path: str | None = None
    model: str | None = None
    created_at: datetime


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate, user: CurrentUser, session: SessionDep
) -> SessionRead:
    s = ChatSession(user_uid=user.uid, title=payload.title)
    session.add(s)
    session.commit()
    session.refresh(s)
    return SessionRead(id=s.id, title=s.title, created_at=s.created_at)


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(user: CurrentUser, session: SessionDep) -> list[SessionRead]:
    rows = session.exec(
        select(ChatSession)
        .where(ChatSession.user_uid == user.uid)
        .order_by(ChatSession.created_at.desc())
    ).all()
    return [SessionRead(id=r.id, title=r.title, created_at=r.created_at) for r in rows]


@router.get("/sessions/search", response_model=list[SessionRead])
def search_sessions(q: str, user: CurrentUser, session: SessionDep) -> list[SessionRead]:
    """Search the user's chat sessions, newest-first. `q` is matched case-insensitively against
    the session title AND the text of every message in the session (both user and assistant),
    so you can find a chat by anything that was said in it."""
    term = q.strip()
    if not term:
        return []
    like = f"%{term}%"
    # Session ids that have at least one matching message (either role).
    matched_rows = session.exec(
        select(ChatMessage.session_id)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.user_uid == user.uid)
        .where(ChatMessage.content.ilike(like))  # type: ignore[attr-defined]
    ).all()
    matched_ids = {r if isinstance(r, int) else r[0] for r in matched_rows}

    rows = session.exec(
        select(ChatSession)
        .where(ChatSession.user_uid == user.uid)
        .order_by(ChatSession.created_at.desc())
    ).all()
    out = [
        r for r in rows if r.id in matched_ids or term.lower() in (r.title or "").lower()
    ]
    return [SessionRead(id=r.id, title=r.title, created_at=r.created_at) for r in out]


def _owned_session(session_id: int, user_uid: str, db) -> ChatSession:
    s = db.get(ChatSession, session_id)
    if s is None or s.user_uid != user_uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return s


_DEFAULT_TITLES = {"New chat", "new chat", ""}


def _auto_title_from(text: str, max_len: int = 50) -> str:
    """Take the first line of the user's message and truncate. Slash-commands are kept verbatim
    (stripping the cmd produced meaningless titles like "250" for `/water 250`)."""
    cleaned = text.strip().split("\n", 1)[0].strip()
    if not cleaned:
        return "New chat"
    return cleaned[: max_len - 1].rstrip() + "…" if len(cleaned) > max_len else cleaned


def _maybe_retitle(s: ChatSession, first_user_text: str, db) -> None:
    """Instant fallback title from the first message (truncation). The LLM refines it later via
    `_maybe_llm_title`, but this guarantees a sensible title even if titling fails or is slow."""
    if (s.title or "").strip() in _DEFAULT_TITLES:
        s.title = _auto_title_from(first_user_text)
        db.add(s)
        db.commit()
        db.refresh(s)


async def _maybe_llm_title(
    session: Session, s: ChatSession, user_text: str, assistant_text: str
) -> str | None:
    """On the first complete turn only, replace the truncation title with a lightweight
    LLM-generated one. Returns the new title if it changed, else None. Best-effort."""
    msg_count = len(
        session.exec(select(ChatMessage.id).where(ChatMessage.session_id == s.id)).all()
    )
    if msg_count > 2:  # only the first user+assistant turn
        return None
    title = await run_in_threadpool(generate_session_title, user_text, assistant_text)
    if not title or title == s.title:
        return None
    s.title = title
    session.add(s)
    session.commit()
    session.refresh(s)
    return title


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user: CurrentUser, session: SessionDep) -> None:
    s = _owned_session(session_id, user.uid, session)
    session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id))
    for msg in session.exec(select(ChatMessage).where(ChatMessage.session_id == s.id)).all():
        session.delete(msg)
    session.delete(s)
    session.commit()


@router.get("/sessions/{session_id}/messages", response_model=list[MessageRead])
def list_messages(session_id: int, user: CurrentUser, session: SessionDep) -> list[MessageRead]:
    _owned_session(session_id, user.uid, session)
    rows = session.exec(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
    ).all()
    return [
        MessageRead(
            id=r.id,
            role=r.role,
            content=r.content,
            image_path=r.image_path,
            model=r.model,
            created_at=r.created_at,
        )
        for r in rows
    ]


# Some fallback models (notably Llama via Groq/OpenRouter) occasionally emit a tool call in
# their native TEXT format instead of the structured tool-call channel. Pydantic AI can't
# intercept that, so the raw token leaks into the reply. Strip it so the user never sees garbage
# like `<function=search_nutrition{"query": "..."}>`.
_TOOL_LEAK_RE = re.compile(
    r"<\|python_tag\|>.*\Z"  # Llama 3.1 python_tag prefix
    r"|<function=[^>]*?>.*?</function>"  # <function=name ...>...</function>
    r"|<function\b.*\Z"  # unclosed <function=name{...}
    r"|<tool_call>.*?</tool_call>",  # generic <tool_call> wrappers
    re.DOTALL | re.IGNORECASE,
)


def _clean_agent_text(text: str) -> str:
    """Strip leaked tool-call tokens and fall back to a friendly message if nothing remains."""
    cleaned = _TOOL_LEAK_RE.sub("", text).strip()
    if not cleaned:
        return "Sorry — I couldn't complete that just now. Could you rephrase or try again?"
    return cleaned


async def _run_agent_turn(
    s: ChatSession,
    content: str,
    image_path: str | None,
    user: User,
    session: Session,
) -> ChatMessage:
    """Persist the user message, run the agent over the session history, and persist + return
    the assistant reply. Shared by the path-based and the unified send endpoints."""
    user_msg = ChatMessage(
        session_id=s.id, role="user", content=content, image_path=image_path
    )
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)
    _maybe_retitle(s, content, session)

    task = _build_task(session, s.id, content, image_path)
    user_key = _user_gemini_key(session, user)
    agent = build_agent(session, user, user_gemini_key=user_key)

    raw = await _run_agent_or_raise(
        agent, task, has_own_key=user_key is not None, is_anonymous=user.is_anonymous
    )
    text = _clean_agent_text(raw)

    assistant_msg = ChatMessage(
        session_id=s.id, role="assistant", content=text, model=used_model_id(agent.model)
    )
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)
    return assistant_msg


def _assistant_read(msg: ChatMessage) -> MessageRead:
    return MessageRead(
        id=msg.id,
        role="assistant",
        content=msg.content,
        image_path=None,
        model=msg.model,
        created_at=msg.created_at,
    )


@router.post("/sessions/{session_id}/messages", response_model=MessageRead)
async def post_message(
    session_id: int,
    payload: MessagePayload,
    user: CurrentUser,
    session: SessionDep,
) ->MessageRead:
    """Append a message to an existing session, run the agent, return the assistant reply."""
    s = _owned_session(session_id, user.uid, session)
    assistant_msg = await _run_agent_turn(
        s, payload.content, payload.image_path, user, session
    )
    return _assistant_read(assistant_msg)


class SendMessagePayload(BaseModel):
    """Unified send: omit `session_id` to lazily create a new session in the same call."""

    session_id: int | None = None
    content: str
    image_path: str | None = None


class SendMessageResponse(BaseModel):
    session_id: int
    session_title: str
    session_created_at: datetime
    is_new_session: bool
    message: MessageRead


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(
    payload: SendMessagePayload,
    user: CurrentUser,
    session: SessionDep,
) ->SendMessageResponse:
    """Create-or-append in a single round-trip. With no `session_id` a fresh session is created;
    otherwise the message is attached to the owned session. Returns the resolved session
    metadata plus the assistant reply, so the client never needs a separate create call."""
    if payload.session_id is None:
        s = ChatSession(user_uid=user.uid, title="New chat")
        session.add(s)
        session.commit()
        session.refresh(s)
        is_new = True
    else:
        s = _owned_session(payload.session_id, user.uid, session)
        is_new = False

    assistant_msg = await _run_agent_turn(
        s, payload.content, payload.image_path, user, session
    )
    # Refine the title with a lightweight LLM call on the first turn (updates s.title in place).
    await _maybe_llm_title(session, s, payload.content, assistant_msg.content)
    return SendMessageResponse(
        session_id=s.id,
        session_title=s.title,
        session_created_at=s.created_at,
        is_new_session=is_new,
        message=_assistant_read(assistant_msg),
    )


class CommandPayload(BaseModel):
    cmd: str
    text: str = ""
    session_id: int | None = None


@router.post("/commands")
async def dispatch_command(
    payload: CommandPayload, user: CurrentUser, session: SessionDep
) -> dict:
    """Slash-command dispatcher. Wraps the input as `/<cmd> <text>` and runs the agent.

    Frontend may also just send `/<cmd> <text>` as a regular message — this endpoint
    exists so deterministic UIs (like a barcode scan that runs without LLM round-trips)
    can short-circuit later. For now it always routes through the agent.
    """
    task = f"User: /{payload.cmd} {payload.text}".strip()
    user_key = _user_gemini_key(session, user)
    agent = build_agent(session, user, user_gemini_key=user_key)
    raw = await _run_agent_or_raise(
        agent, task, has_own_key=user_key is not None, is_anonymous=user.is_anonymous
    )
    return {"text": _clean_agent_text(raw), "cmd": payload.cmd}


async def _safe_send(ws: WebSocket, data: dict) -> bool:
    """Send JSON, returning False if the socket has gone away (client navigated/closed)."""
    try:
        await ws.send_json(data)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, session: SessionDep) -> None:
    """Interactive chat over WebSocket. Emits, in order:
        {type: 'session', ...}                  — resolved/created session metadata
        {type: 'tool', name}                    — each time the agent invokes a tool (live)
        {type: 'message', message}              — the final assistant reply
        {type: 'done'} | {type: 'error', message}

    Auth is via a `?token=` query param because browsers can't set headers on a WS handshake.
    One message per connection: the client opens a socket, sends one payload, reads events, done.
    """
    await websocket.accept()

    # --- Authenticate (query param) + resolve user ---
    try:
        decoded = decode_token(websocket.query_params.get("token", ""))
        user = get_current_user(decoded, session)
    except HTTPException:
        await _safe_send(websocket, {"type": "error", "message": "Authentication failed. Please sign in again."})
        await websocket.close()
        return

    # --- Read the single request payload ---
    try:
        payload = await websocket.receive_json()
    except (WebSocketDisconnect, ValueError):
        await websocket.close()
        return

    content = (payload.get("content") or "").strip()
    image_path = payload.get("image_path")
    session_id = payload.get("session_id")
    if not content and not image_path:
        await _safe_send(websocket, {"type": "error", "message": "Empty message."})
        await websocket.close()
        return

    # --- Resolve or create the session ---
    if session_id is None:
        s = ChatSession(user_uid=user.uid, title="New chat")
        session.add(s)
        session.commit()
        session.refresh(s)
        is_new = True
    else:
        s = session.get(ChatSession, session_id)
        if s is None or s.user_uid != user.uid:
            await _safe_send(websocket, {"type": "error", "message": "Session not found."})
            await websocket.close()
            return
        is_new = False

    # --- Persist the user message + auto-title ---
    user_msg = ChatMessage(session_id=s.id, role="user", content=content, image_path=image_path)
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)
    _maybe_retitle(s, content, session)

    await _safe_send(
        websocket,
        {
            "type": "session",
            "session_id": s.id,
            "session_title": s.title,
            "session_created_at": s.created_at.isoformat(),
            "is_new_session": is_new,
        },
    )

    # --- Stream the agent run, forwarding tool events live ---
    task = _build_task(session, s.id, content, image_path)
    user_key = _user_gemini_key(session, user)
    agent = build_agent(session, user, user_gemini_key=user_key)

    from smolagents.memory import FinalAnswerStep  # local import keeps module load cheap

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker() -> None:
        # Runs in a thread: smolagents' run(stream=True) is a sync generator that blocks on the
        # LLM. Tools execute sequentially here, so the DB session is only touched by this thread
        # while the main coroutine just drains the queue (no concurrent session access).
        try:
            for ev in agent.run(task, stream=True):
                loop.call_soon_threadsafe(queue.put_nowait, ("event", ev))
        except Exception as exc:  # noqa: BLE001 — forwarded + classified on the main side
            loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    fut = loop.run_in_executor(None, _worker)
    final_text = ""
    error_exc: Exception | None = None
    try:
        while True:
            kind, item = await queue.get()
            if kind == "done":
                break
            if kind == "error":
                error_exc = item
                continue  # a 'done' sentinel always follows
            ev = item
            if isinstance(ev, FinalAnswerStep):
                final_text = str(getattr(ev, "output", "") or "")
            elif type(ev).__name__ == "ToolCall":
                name = getattr(ev, "name", None)
                if name and name != "final_answer":
                    await _safe_send(websocket, {"type": "tool", "name": name})
    finally:
        await fut

    if error_exc is not None:
        logger.warning("agent ws run failed: %s", " ".join(str(error_exc).split())[:160])
        await _safe_send(
            websocket,
            {
                "type": "error",
                "message": _friendly_provider_error(
                    error_exc, has_own_key=user_key is not None, is_anonymous=user.is_anonymous
                ),
            },
        )
        await websocket.close()
        return

    text = _clean_agent_text(final_text)
    assistant_msg = ChatMessage(
        session_id=s.id, role="assistant", content=text, model=used_model_id(agent.model)
    )
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)

    await _safe_send(
        websocket,
        {
            "type": "message",
            "message": {
                "id": assistant_msg.id,
                "role": "assistant",
                "content": assistant_msg.content,
                "image_path": None,
                "model": assistant_msg.model,
                "created_at": assistant_msg.created_at.isoformat(),
            },
        },
    )
    # Refine the title (first turn only) and push it so Recents + the header update live.
    new_title = await _maybe_llm_title(session, s, content, text)
    if new_title:
        await _safe_send(websocket, {"type": "title", "session_id": s.id, "title": new_title})
    await _safe_send(websocket, {"type": "done"})
    await websocket.close()
