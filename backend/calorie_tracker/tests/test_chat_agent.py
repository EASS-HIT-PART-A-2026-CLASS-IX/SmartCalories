from __future__ import annotations

from fastapi.testclient import TestClient
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
    Model,
)

from calorie_tracker.main import app


def _tool_call(name: str, args: dict) -> ChatMessage:
    return ChatMessage(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=[
            ChatMessageToolCall(
                id=f"call_{name}",
                type="function",
                function=ChatMessageToolCallFunction(name=name, arguments=args),
            )
        ],
    )


class ScriptedModel(Model):
    """Deterministic stand-in for a real LLM: replays a fixed sequence of tool calls.

    End every script with a `final_answer` call so the ToolCallingAgent terminates.
    """

    def __init__(self, actions: list[tuple[str, dict]]):
        super().__init__()
        self._actions = actions
        self._i = 0

    def generate(self, messages, **kwargs) -> ChatMessage:  # type: ignore[override]
        name, args = self._actions[min(self._i, len(self._actions) - 1)]
        self._i += 1
        return _tool_call(name, args)


def _final(text: str) -> ScriptedModel:
    """A model that immediately answers with `text` (no other tools)."""
    return ScriptedModel([("final_answer", {"answer": text})])


def _use_model(monkeypatch, model: Model) -> None:
    monkeypatch.setattr("calorie_tracker.ai.agent.get_default_model", lambda: model)


def test_create_and_list_sessions(client: TestClient) -> None:
    r = client.post("/chat/sessions", json={"title": "Diet check"})
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.get("/chat/sessions")
    assert r.status_code == 200
    assert any(s["id"] == sid for s in r.json())


def test_post_message_returns_assistant_text(client: TestClient, monkeypatch) -> None:
    sid = client.post("/chat/sessions", json={"title": "X"}).json()["id"]
    _use_model(monkeypatch, _final("Logged: oatmeal 300 kcal."))
    r = client.post(
        f"/chat/sessions/{sid}/messages",
        json={"content": "/log oatmeal 300 kcal breakfast"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "assistant"
    assert body["content"] == "Logged: oatmeal 300 kcal."


def test_messages_persisted_to_session(client: TestClient, monkeypatch) -> None:
    sid = client.post("/chat/sessions", json={"title": "Y"}).json()["id"]
    _use_model(monkeypatch, _final("Hello!"))
    client.post(f"/chat/sessions/{sid}/messages", json={"content": "Hi"})

    msgs = client.get(f"/chat/sessions/{sid}/messages").json()
    assert len(msgs) == 2
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant"]
    assert msgs[1]["content"] == "Hello!"


def test_unified_send_creates_session(client: TestClient, monkeypatch) -> None:
    """POST /chat/messages with no session_id lazily creates one in a single call."""
    _use_model(monkeypatch, _final("Welcome!"))
    r = client.post("/chat/messages", json={"content": "first message"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_new_session"] is True
    assert body["message"]["content"] == "Welcome!"
    # The session now exists and holds the user + assistant turn.
    msgs = client.get(f"/chat/sessions/{body['session_id']}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_session_isolation(client: TestClient, user2_client: TestClient) -> None:
    sid = client.post("/chat/sessions", json={"title": "Mine"}).json()["id"]
    r = user2_client.get(f"/chat/sessions/{sid}/messages")
    assert r.status_code == 404


def test_search_sessions_matches_message_content(client: TestClient, monkeypatch) -> None:
    """Search finds a session by text in ANY of its messages (user or assistant), newest-first,
    and never leaks another user's chats."""
    sid = client.post("/chat/sessions", json={"title": "Lunch plans"}).json()["id"]
    _use_model(monkeypatch, _final("Sure — quinoa salad is a great option."))
    client.post(f"/chat/sessions/{sid}/messages", json={"content": "what about quinoa?"})

    # Match on a word that only appears in the user message.
    hits = client.get("/chat/sessions/search", params={"q": "quinoa"}).json()
    assert [s["id"] for s in hits] == [sid]

    # Match on a word that only appears in the assistant reply.
    hits = client.get("/chat/sessions/search", params={"q": "salad"}).json()
    assert sid in [s["id"] for s in hits]

    # Match on the title.
    hits = client.get("/chat/sessions/search", params={"q": "lunch"}).json()
    assert sid in [s["id"] for s in hits]

    # No false positives.
    assert client.get("/chat/sessions/search", params={"q": "zzzznope"}).json() == []


def test_search_sessions_is_user_scoped(
    client: TestClient, user2_client: TestClient, monkeypatch
) -> None:
    sid = client.post("/chat/sessions", json={"title": "Private"}).json()["id"]
    _use_model(monkeypatch, _final("secret pancakes"))
    client.post(f"/chat/sessions/{sid}/messages", json={"content": "tell me about pancakes"})

    # Other user must not see it.
    assert user2_client.get("/chat/sessions/search", params={"q": "pancakes"}).json() == []


def test_command_dispatch_routes_through_agent(client: TestClient, monkeypatch) -> None:
    _use_model(monkeypatch, _final("today: 0 kcal"))
    r = client.post("/chat/commands", json={"cmd": "macros", "text": ""})
    assert r.status_code == 200
    assert r.json()["cmd"] == "macros"
    assert "kcal" in r.json()["text"]


def test_log_food_tool_creates_diary_entry(client: TestClient, monkeypatch) -> None:
    """Script the agent to call log_food, then finalize — exercises the real tool + DB write."""
    sid = client.post("/chat/sessions", json={"title": "Log via agent"}).json()["id"]
    _use_model(
        monkeypatch,
        ScriptedModel(
            [
                ("log_food", {"name": "Apple", "calories": 95, "meal": "snack"}),
                ("final_answer", {"answer": "Logged the apple — 95 kcal."}),
            ]
        ),
    )
    r = client.post(f"/chat/sessions/{sid}/messages", json={"content": "/log Apple 95 snack"})
    assert r.status_code == 200
    diary = client.get("/diary").json()
    assert len(diary) >= 1
    assert any(d["source"] == "agent" for d in diary)


def test_update_food_tool_edits_entry(client: TestClient, monkeypatch) -> None:
    """Agent edits an existing diary entry by id via update_food."""
    entry = client.post("/diary", json={"name": "Toast", "calories": 100, "meal": "breakfast"}).json()
    sid = client.post("/chat/sessions", json={"title": "Edit"}).json()["id"]
    _use_model(
        monkeypatch,
        ScriptedModel(
            [
                ("update_food", {"entry_id": entry["id"], "calories": 250}),
                ("final_answer", {"answer": "Updated to 250 kcal."}),
            ]
        ),
    )
    client.post(f"/chat/sessions/{sid}/messages", json={"content": "make my toast 250"})
    after = client.get("/diary").json()
    edited = next(d for d in after if d["id"] == entry["id"])
    assert edited["calories"] == 250


def test_delete_food_tool_removes_entry(client: TestClient, monkeypatch) -> None:
    """Agent deletes a diary entry by id via delete_food."""
    entry = client.post("/diary", json={"name": "Cookie", "calories": 200, "meal": "snack"}).json()
    sid = client.post("/chat/sessions", json={"title": "Delete"}).json()["id"]
    _use_model(
        monkeypatch,
        ScriptedModel(
            [
                ("delete_food", {"entry_id": entry["id"]}),
                ("final_answer", {"answer": "Removed the cookie."}),
            ]
        ),
    )
    client.post(f"/chat/sessions/{sid}/messages", json={"content": "delete the cookie"})
    after = client.get("/diary").json()
    assert all(d["id"] != entry["id"] for d in after)


def test_ws_streams_tool_events_then_message(client: TestClient, monkeypatch) -> None:
    """The WebSocket emits a session event, a live tool event, then the final message + done."""
    from calorie_tracker.routers import chat as chat_router

    # WS auth is via ?token= → decode_token (not the header dependency). Map any token to user-1.
    monkeypatch.setattr(
        chat_router,
        "decode_token",
        lambda token: {"uid": "user-1-uid", "email": "u1@example.com", "role": "user"},
    )
    _use_model(
        monkeypatch,
        ScriptedModel(
            [
                (
                    "compute_tdee",
                    {"weight_kg": 70, "height_cm": 175, "age_years": 30, "sex": "male"},
                ),
                ("final_answer", {"answer": "Your TDEE is about 2,556 kcal."}),
            ]
        ),
    )

    events = []
    with client.websocket_connect("/chat/ws?token=user-1") as ws:
        ws.send_json({"content": "compute my tdee", "session_id": None})
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev["type"] in ("done", "error"):
                break

    types = [e["type"] for e in events]
    assert types[0] == "session"
    assert events[0]["is_new_session"] is True
    assert any(e["type"] == "tool" and e["name"] == "compute_tdee" for e in events)
    msg = next(e for e in events if e["type"] == "message")
    assert msg["message"]["content"] == "Your TDEE is about 2,556 kcal."
    assert types[-1] == "done"


def test_session_title_generated_by_llm(client: TestClient, monkeypatch) -> None:
    """On the first turn the title is refined by a lightweight LLM call (separate model hook)."""
    from calorie_tracker.ai import agent as agent_mod

    class TitleModel(Model):
        def generate(self, messages, **kwargs):  # type: ignore[override]
            return ChatMessage(role=MessageRole.ASSISTANT, content='"Quinoa Lunch Ideas."')

    monkeypatch.setattr(agent_mod, "get_title_model", lambda: TitleModel())
    _use_model(monkeypatch, _final("Quinoa is a great lunch base."))

    r = client.post("/chat/messages", json={"content": "what about quinoa for lunch?"})
    assert r.status_code == 200
    # Quotes + trailing period stripped by _clean_title.
    assert r.json()["session_title"] == "Quinoa Lunch Ideas"


def test_provider_error_returns_friendly_message(client: TestClient, monkeypatch) -> None:
    """A provider rate-limit error surfaces as a clear 503 message, not a raw 500."""

    class RateLimitedModel(Model):
        def generate(self, messages, **kwargs):  # type: ignore[override]
            raise RuntimeError("litellm.RateLimitError: 429 RESOURCE_EXHAUSTED quota exceeded")

    _use_model(monkeypatch, RateLimitedModel())
    sid = client.post("/chat/sessions", json={"title": "Err"}).json()["id"]
    r = client.post(f"/chat/sessions/{sid}/messages", json={"content": "hi"})
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    assert "rate-limited" in detail or "rate limit" in detail
    # Non-anonymous user without their own key gets the "add your own key" tip.
    assert "settings" in detail
