"""SSE adapter that turns Pydantic AI's run graph into typed events for the frontend.

Event protocol matches `.claude/plans/ex3-master-plan.md`:
  start | thinking | tool_call | tool_result | token | error | done

Pacing
------
TestModel and (sometimes) real Gemini emit text in big chunks, which makes the chat UI flash
the entire reply at once. We split any "fat" token delta into word-sized pieces and yield each
with `stream_token_delay_ms` between them so the frontend's typewriter cursor has something to
animate. Set `STREAM_TOKEN_DELAY_MS=0` (env) to disable pacing entirely.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncIterator

from pydantic_ai import Agent

from ..config import get_settings
from .agent import AgentDeps

logger = logging.getLogger(__name__)

_WORD_SPLIT = re.compile(r"(\s+)")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _split_into_chunks(text: str) -> list[str]:
    """Word-level chunks that preserve the original whitespace so reassembling = original."""
    parts = _WORD_SPLIT.split(text)
    return [p for p in parts if p != ""]


async def stream_agent_run(
    agent: Agent,
    prompt,
    deps: AgentDeps,
    message_id: str,
    message_history: list | None = None,
) -> AsyncIterator[str]:
    settings = get_settings()
    token_delay = settings.stream_token_delay_ms / 1000.0
    thinking_delay = settings.stream_thinking_delay_ms / 1000.0
    tool_delay = settings.stream_tool_delay_ms / 1000.0

    yield _sse("start", {"message_id": message_id})
    yield _sse("thinking", {"phase": "reasoning"})
    if thinking_delay > 0:
        await asyncio.sleep(thinking_delay)

    final_text = ""
    iter_kwargs: dict = {"deps": deps}
    if message_history:
        iter_kwargs["message_history"] = message_history
    try:
        async with agent.iter(prompt, **iter_kwargs) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as stream:
                        async for event in stream:
                            payload = _classify_request_event(event)
                            if payload is None:
                                continue
                            kind, data = payload
                            if kind == "token":
                                async for frame in _paced_token_frames(
                                    data.get("delta", ""), token_delay
                                ):
                                    yield frame
                                final_text += data.get("delta", "")
                            else:
                                yield _sse(kind, data)
                                if kind == "tool_call" and tool_delay > 0:
                                    await asyncio.sleep(tool_delay)
                elif Agent.is_call_tools_node(node):
                    async with node.stream(run.ctx) as stream:
                        async for event in stream:
                            payload = _classify_tool_event(event)
                            if payload is None:
                                continue
                            kind, data = payload
                            yield _sse(kind, data)
                            if tool_delay > 0:
                                await asyncio.sleep(tool_delay)
                elif Agent.is_end_node(node):
                    output = run.result.output if run.result else final_text
                    if output and output != final_text:
                        # The model returned a final text we never saw as deltas
                        # (e.g. TestModel's `custom_output_text`). Stream it now.
                        leftover = output[len(final_text) :] if output.startswith(final_text) else output
                        async for frame in _paced_token_frames(leftover, token_delay):
                            yield frame
                        final_text = output
                    break
        yield _sse("done", {"message_id": message_id, "text": final_text})
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent stream failed")
        msg = str(exc)
        if "output validation" in msg or "UnexpectedModelBehavior" in type(exc).__name__:
            msg = "The AI model returned an unexpected response. Please try again."
        yield _sse("error", {"message": msg})


async def _paced_token_frames(delta: str, delay: float) -> AsyncIterator[str]:
    """Yield one or more `token` SSE frames for `delta`, pacing word-by-word."""
    if not delta:
        return
    if delay <= 0 or len(delta) <= 8:
        yield _sse("token", {"delta": delta})
        return
    for chunk in _split_into_chunks(delta):
        yield _sse("token", {"delta": chunk})
        if not chunk.isspace():
            await asyncio.sleep(delay)


def _classify_request_event(event) -> tuple[str, dict] | None:
    name = type(event).__name__
    if name == "PartStartEvent":
        part = getattr(event, "part", None)
        part_type = type(part).__name__ if part is not None else ""
        if part_type == "ToolCallPart":
            return "tool_call", {
                "name": getattr(part, "tool_name", "unknown"),
                "args_preview": str(getattr(part, "args", ""))[:200],
            }
        if part_type == "TextPart":
            content = getattr(part, "content", "")
            return ("token", {"delta": content}) if content else None
    if name == "PartDeltaEvent":
        delta = getattr(event, "delta", None)
        delta_type = type(delta).__name__ if delta is not None else ""
        if delta_type == "TextPartDelta":
            content = getattr(delta, "content_delta", "")
            return ("token", {"delta": content}) if content else None
    if name == "FinalResultEvent":
        return None
    return None


def _classify_tool_event(event) -> tuple[str, dict] | None:
    name = type(event).__name__
    if name == "FunctionToolCallEvent":
        part = getattr(event, "part", None)
        return "tool_call", {
            "name": getattr(part, "tool_name", "unknown") if part else "unknown",
            "args_preview": str(getattr(part, "args", ""))[:200] if part else "",
        }
    if name == "FunctionToolResultEvent":
        result = getattr(event, "result", None)
        tool_name = getattr(result, "tool_name", "unknown") if result else "unknown"
        content = getattr(result, "content", None) if result else None
        return "tool_result", {
            "name": tool_name,
            "summary": str(content)[:300] if content is not None else "",
        }
    return None
