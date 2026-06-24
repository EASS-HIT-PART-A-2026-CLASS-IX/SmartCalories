from __future__ import annotations

from fastapi.testclient import TestClient

GEMINI_KEY = "AIzaSyTESTKEY0123456789abcdefghijklmno"


def test_llm_key_lifecycle(client: TestClient) -> None:
    # Starts empty.
    r = client.get("/me/llm-key")
    assert r.status_code == 200
    assert r.json() == {"has_key": False, "gemini_last4": None}

    # Set a key — response masks it to the last 4 chars and never echoes the raw value.
    r = client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY})
    assert r.status_code == 200
    body = r.json()
    assert body["has_key"] is True
    assert body["gemini_last4"] == GEMINI_KEY[-4:]
    assert GEMINI_KEY not in r.text  # raw key must not leak

    # GET reflects the stored masked status.
    assert client.get("/me/llm-key").json() == {"has_key": True, "gemini_last4": GEMINI_KEY[-4:]}

    # Delete clears it.
    assert client.delete("/me/llm-key").json()["has_key"] is False
    assert client.get("/me/llm-key").json()["has_key"] is False


def test_llm_key_rejects_garbage(client: TestClient) -> None:
    r = client.put("/me/llm-key", json={"gemini_api_key": "short"})
    assert r.status_code == 422


def test_llm_key_blocked_for_anonymous(anon_client: TestClient) -> None:
    assert anon_client.get("/me/llm-key").status_code == 403
    assert anon_client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY}).status_code == 403


def test_llm_key_is_user_scoped(client: TestClient, user2_client: TestClient) -> None:
    client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY})
    # A different user has no key.
    assert user2_client.get("/me/llm-key").json()["has_key"] is False


def test_stored_key_is_encrypted_at_rest(client: TestClient) -> None:
    """The DB must hold a Fernet token, not the plaintext key."""
    from calorie_tracker import db as db_module
    from calorie_tracker.models import UserLLMKey
    from sqlmodel import Session

    client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY})
    with Session(db_module._engine) as s:
        row = s.get(UserLLMKey, "user-1-uid")
        assert row is not None
        assert row.gemini_key_enc and row.gemini_key_enc != GEMINI_KEY
        assert GEMINI_KEY not in row.gemini_key_enc
