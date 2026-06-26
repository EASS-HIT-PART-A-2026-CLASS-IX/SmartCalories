from __future__ import annotations

from fastapi.testclient import TestClient

GEMINI_KEY = "AIzaSyTESTKEY0123456789abcdefghijklmno"
ANTHROPIC_KEY = "sk-ant-api03-TESTKEY0123456789abcdefghijklmno"
GROQ_KEY = "gsk_TESTKEY0123456789abcdefghijklmnopqrst"
OPENROUTER_KEY = "sk-or-v1-TESTKEY0123456789abcdefghijklmno"


def test_llm_key_lifecycle(client: TestClient) -> None:
    # Starts empty.
    r = client.get("/me/llm-key")
    assert r.status_code == 200
    assert r.json() == {
        "has_anthropic": False,
        "anthropic_last4": None,
        "has_gemini": False,
        "gemini_last4": None,
        "has_groq": False,
        "groq_last4": None,
        "has_openrouter": False,
        "openrouter_last4": None,
    }

    # Set all four keys — response masks them to the last 4 chars and never echoes raw values.
    r = client.put(
        "/me/llm-key",
        json={
            "gemini_api_key": GEMINI_KEY,
            "anthropic_api_key": ANTHROPIC_KEY,
            "groq_api_key": GROQ_KEY,
            "openrouter_api_key": OPENROUTER_KEY,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_gemini"] is True and body["gemini_last4"] == GEMINI_KEY[-4:]
    assert body["has_anthropic"] is True and body["anthropic_last4"] == ANTHROPIC_KEY[-4:]
    assert body["has_groq"] is True and body["groq_last4"] == GROQ_KEY[-4:]
    assert body["has_openrouter"] is True and body["openrouter_last4"] == OPENROUTER_KEY[-4:]
    for raw in (GEMINI_KEY, ANTHROPIC_KEY, GROQ_KEY, OPENROUTER_KEY):
        assert raw not in r.text  # raw keys must not leak

    # Clearing just one provider (empty string) leaves the others intact.
    r = client.put("/me/llm-key", json={"gemini_api_key": ""})
    body = r.json()
    assert body["has_gemini"] is False
    assert body["has_anthropic"] is True
    assert body["has_groq"] is True
    assert body["has_openrouter"] is True

    # Delete clears all.
    after = client.delete("/me/llm-key").json()
    assert after["has_anthropic"] is False and after["has_groq"] is False
    assert client.get("/me/llm-key").json()["has_openrouter"] is False


def test_llm_key_rejects_garbage(client: TestClient) -> None:
    assert client.put("/me/llm-key", json={"gemini_api_key": "short"}).status_code == 422
    # Wrong prefix for each provider.
    assert client.put("/me/llm-key", json={"gemini_api_key": "sk-ant-xxxxxxxxxxxxxxxxxx"}).status_code == 422
    assert client.put("/me/llm-key", json={"anthropic_api_key": "AIzaxxxxxxxxxxxxxxxxxx"}).status_code == 422
    assert client.put("/me/llm-key", json={"groq_api_key": "sk-or-xxxxxxxxxxxxxxxxxx"}).status_code == 422
    assert client.put("/me/llm-key", json={"openrouter_api_key": "gsk_xxxxxxxxxxxxxxxxxx"}).status_code == 422


def test_llm_key_blocked_for_anonymous(anon_client: TestClient) -> None:
    assert anon_client.get("/me/llm-key").status_code == 403
    assert anon_client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY}).status_code == 403


def test_llm_key_is_user_scoped(client: TestClient, user2_client: TestClient) -> None:
    client.put("/me/llm-key", json={"gemini_api_key": GEMINI_KEY})
    # A different user has no key.
    assert user2_client.get("/me/llm-key").json()["has_gemini"] is False


def test_stored_keys_are_encrypted_at_rest(client: TestClient) -> None:
    """The DB must hold Fernet tokens, not the plaintext keys."""
    from calorie_tracker import db as db_module
    from calorie_tracker.models import UserLLMKey
    from sqlmodel import Session

    client.put(
        "/me/llm-key", json={"gemini_api_key": GEMINI_KEY, "anthropic_api_key": ANTHROPIC_KEY}
    )
    with Session(db_module._engine) as s:
        row = s.get(UserLLMKey, "user-1-uid")
        assert row is not None
        assert row.gemini_key_enc and GEMINI_KEY not in row.gemini_key_enc
        assert row.anthropic_key_enc and ANTHROPIC_KEY not in row.anthropic_key_enc
