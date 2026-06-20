from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from sqlmodel import select

from ..ai.agent import AgentDeps, agent as ai_agent
from ..ai.streaming import stream_agent_run
from ..deps import CurrentUser, SessionDep
from ..models import ChatMessage, ChatSession
from ..services.cache import AsyncCache, get_cache

logger = logging.getLogger(__name__)


def _media_type_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")


def _build_user_prompt(content: str, image_path: str | None) -> str | list[Any]:
    """Wrap text + optional image into the multimodal sequence Pydantic AI expects."""
    if not image_path:
        return content
    p = Path(image_path)
    if not p.is_file():
        logger.warning("image_path not on disk, falling back to text-only: %s", image_path)
        return content
    try:
        return [content, BinaryContent(data=p.read_bytes(), media_type=_media_type_for(image_path))]
    except OSError as exc:
        logger.warning("could not read %s: %s", image_path, exc)
        return content


def _history_for(session, session_id: int, exclude_id: int | None) -> list:
    """Convert prior ChatMessage rows into Pydantic AI ModelRequest/ModelResponse.

    Image bytes are NOT replayed — the chat-room transcript stays text only — but the agent
    keeps continuity of the conversation. Tool-call rows are skipped (they are reconstructed
    by the model from the current turn's tools).
    """
    rows = session.exec(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)
    ).all()
    out: list = []
    for r in rows:
        if exclude_id is not None and r.id == exclude_id:
            continue
        if r.role == "user":
            out.append(ModelRequest(parts=[UserPromptPart(content=r.content or "")]))
        elif r.role == "assistant" and r.content:
            out.append(ModelResponse(parts=[TextPart(content=r.content)]))
    return out

router = APIRouter(prefix="/chat", tags=["chat"])

CacheDep = Annotated[AsyncCache, Depends(get_cache)]


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
    if (s.title or "").strip() in _DEFAULT_TITLES:
        s.title = _auto_title_from(first_user_text)
        db.add(s)
        db.commit()
        db.refresh(s)


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
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/sessions/{session_id}/messages", response_model=MessageRead)
async def post_message(
    session_id: int,
    payload: MessagePayload,
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
) -> MessageRead:
    """Non-streaming send. Persists user message, runs the agent, returns the assistant reply.

    Use POST /sessions/{id}/stream for the SSE streaming variant.
    """
    s = _owned_session(session_id, user.uid, session)
    user_msg = ChatMessage(
        session_id=s.id, role="user", content=payload.content, image_path=payload.image_path
    )
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)
    _maybe_retitle(s, payload.content, session)

    history = _history_for(session, s.id, exclude_id=user_msg.id)
    prompt = _build_user_prompt(payload.content, payload.image_path)

    deps = AgentDeps(session=session, user=user, cache=cache, request_id=str(uuid.uuid4()))
    result = await run_in_threadpool(
        lambda: ai_agent.run_sync(prompt, deps=deps, message_history=history)
    )
    text = result.output if hasattr(result, "output") else str(result)

    assistant_msg = ChatMessage(session_id=s.id, role="assistant", content=text)
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)
    return MessageRead(
        id=assistant_msg.id,
        role="assistant",
        content=assistant_msg.content,
        image_path=None,
        created_at=assistant_msg.created_at,
    )


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: int,
    payload: MessagePayload,
    user: CurrentUser,
    session: SessionDep,
    cache: CacheDep,
) -> StreamingResponse:
    """ChatGPT-style SSE: emits start/thinking/tool_call/tool_result/token/done/error events."""
    s = _owned_session(session_id, user.uid, session)
    user_msg = ChatMessage(
        session_id=s.id, role="user", content=payload.content, image_path=payload.image_path
    )
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)
    _maybe_retitle(s, payload.content, session)
    message_id = str(uuid.uuid4())

    history = _history_for(session, s.id, exclude_id=user_msg.id)
    prompt = _build_user_prompt(payload.content, payload.image_path)

    async def gen():
        import json as _json

        async for frame in stream_agent_run(
            ai_agent,
            prompt,
            AgentDeps(session=session, user=user, cache=cache, request_id=message_id),
            message_id=message_id,
            message_history=history,
        ):
            # Persist the assistant message BEFORE yielding the `done` frame so the DB row
            # exists by the time the frontend receives `done` and immediately refetches messages.
            if frame.startswith("event: done"):
                text = ""
                for line in frame.splitlines():
                    if line.startswith("data:"):
                        try:
                            data = _json.loads(line[5:].strip())
                            text = data.get("text", "") or text
                        except ValueError:
                            pass
                assistant_msg = ChatMessage(session_id=s.id, role="assistant", content=text)
                session.add(assistant_msg)
                session.commit()
            yield frame

    return StreamingResponse(gen(), media_type="text/event-stream")


class CommandPayload(BaseModel):
    cmd: str
    text: str = ""
    session_id: int | None = None


@router.post("/commands")
async def dispatch_command(
    payload: CommandPayload, user: CurrentUser, session: SessionDep, cache: CacheDep
) -> dict:
    """Slash-command dispatcher. Wraps the input as `/<cmd> <text>` and runs the agent.

    Frontend may also just send `/<cmd> <text>` as a regular message — this endpoint
    exists so deterministic UIs (like a barcode scan that runs without LLM round-trips)
    can short-circuit later. For now it always routes through the agent.
    """
    prompt = f"/{payload.cmd} {payload.text}".strip()
    deps = AgentDeps(session=session, user=user, cache=cache, request_id=str(uuid.uuid4()))
    result = await run_in_threadpool(ai_agent.run_sync, prompt, deps=deps)
    text = result.output if hasattr(result, "output") else str(result)
    return {"text": text, "cmd": payload.cmd}
