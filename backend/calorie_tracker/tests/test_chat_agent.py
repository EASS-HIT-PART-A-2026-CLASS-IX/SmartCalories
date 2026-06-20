from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from calorie_tracker.ai.agent import agent as ai_agent
from calorie_tracker.main import app
from calorie_tracker.services.cache import get_cache


class _MemCache:
    def __init__(self):
        self._d: dict[str, str] = {}

    async def get(self, key):
        return self._d.get(key)

    async def set(self, key, value, ttl=3600):
        self._d[key] = value


@pytest.fixture(autouse=True)
def _override_cache():
    cache = _MemCache()
    app.dependency_overrides[get_cache] = lambda: cache
    yield
    app.dependency_overrides.pop(get_cache, None)


def _no_tool_model(text: str = "ok") -> TestModel:
    """TestModel that returns plain text and never invokes tools."""
    return TestModel(custom_output_text=text, call_tools=[])


def test_create_and_list_sessions(client: TestClient) -> None:
    r = client.post("/chat/sessions", json={"title": "Diet check"})
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.get("/chat/sessions")
    assert r.status_code == 200
    assert any(s["id"] == sid for s in r.json())


def test_post_message_returns_assistant_text(client: TestClient) -> None:
    sid = client.post("/chat/sessions", json={"title": "X"}).json()["id"]
    with ai_agent.override(model=_no_tool_model("Logged: oatmeal 300 kcal.")):
        r = client.post(
            f"/chat/sessions/{sid}/messages",
            json={"content": "/log oatmeal 300 kcal breakfast"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "assistant"
    assert body["content"] == "Logged: oatmeal 300 kcal."


def test_messages_persisted_to_session(client: TestClient) -> None:
    sid = client.post("/chat/sessions", json={"title": "Y"}).json()["id"]
    with ai_agent.override(model=_no_tool_model("Hello!")):
        client.post(f"/chat/sessions/{sid}/messages", json={"content": "Hi"})

    msgs = client.get(f"/chat/sessions/{sid}/messages").json()
    assert len(msgs) == 2
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant"]
    assert msgs[1]["content"] == "Hello!"


def test_session_isolation(client: TestClient, user2_client: TestClient) -> None:
    sid = client.post("/chat/sessions", json={"title": "Mine"}).json()["id"]
    r = user2_client.get(f"/chat/sessions/{sid}/messages")
    assert r.status_code == 404


def test_command_dispatch_routes_through_agent(client: TestClient) -> None:
    with ai_agent.override(model=_no_tool_model("today: 0 kcal")):
        r = client.post("/chat/commands", json={"cmd": "macros", "text": ""})
    assert r.status_code == 200
    assert r.json()["cmd"] == "macros"
    assert "kcal" in r.json()["text"]


def test_log_food_tool_creates_diary_entry(client: TestClient) -> None:
    """Restrict TestModel to a single tool so we get deterministic write behaviour."""
    sid = client.post("/chat/sessions", json={"title": "Log via agent"}).json()["id"]
    test_model = TestModel(call_tools=["log_food"])
    with ai_agent.override(model=test_model):
        r = client.post(
            f"/chat/sessions/{sid}/messages",
            json={"content": "/log Apple 95 snack"},
        )
    assert r.status_code == 200
    diary = client.get("/diary").json()
    assert len(diary) >= 1
    assert any(d["source"] == "agent" for d in diary)
