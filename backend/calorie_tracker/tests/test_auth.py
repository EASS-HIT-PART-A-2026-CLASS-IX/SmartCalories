from __future__ import annotations

from fastapi.testclient import TestClient


def test_protected_route_rejects_missing_token(unauth_client: TestClient) -> None:
    r = unauth_client.get("/users/me")
    assert r.status_code == 401


def test_protected_route_rejects_expired_token(unauth_client: TestClient) -> None:
    r = unauth_client.get("/users/me", headers={"Authorization": "Bearer expired"})
    assert r.status_code == 401


def test_me_autocreates_user(client: TestClient) -> None:
    r = client.get("/users/me")
    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "user-1-uid"
    assert body["email"] == "u1@example.com"
    assert body["role"] == "user"
    assert body["is_anonymous"] is False


def test_me_patch(client: TestClient) -> None:
    r = client.patch("/users/me", json={"display_name": "Roei", "locale": "he"})
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Roei"
    assert body["locale"] == "he"


def test_anon_user_flagged(anon_client: TestClient) -> None:
    r = anon_client.get("/users/me")
    assert r.status_code == 200
    body = r.json()
    assert body["is_anonymous"] is True
    assert body["uid"] == "anon-uid"


def test_admin_role_mirrored(admin_client: TestClient) -> None:
    r = admin_client.get("/users/me")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_goals_default_then_upsert(client: TestClient) -> None:
    r = client.get("/users/me/goals")
    assert r.status_code == 200
    assert r.json()["daily_kcal"] is None

    r = client.put(
        "/users/me/goals",
        json={
            "daily_kcal": 2200,
            "protein_g": 140,
            "carb_g": 220,
            "fat_g": 70,
            "dietary_filters": ["vegetarian"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["daily_kcal"] == 2200
    assert body["dietary_filters"] == ["vegetarian"]


def test_preferences_default_then_upsert(client: TestClient) -> None:
    r = client.get("/users/me/preferences")
    assert r.status_code == 200
    assert r.json()["theme"] == "system"

    r = client.put(
        "/users/me/preferences",
        json={"theme": "dark", "language": "he", "units": "metric"},
    )
    assert r.status_code == 200
    assert r.json()["theme"] == "dark"
    assert r.json()["language"] == "he"


def test_diary_isolated_between_users(client: TestClient, user2_client: TestClient) -> None:
    client.post("/diary", json={"name": "U1 lunch", "calories": 500, "meal": "lunch"})
    user2_client.post("/diary", json={"name": "U2 dinner", "calories": 700, "meal": "dinner"})

    u1_list = client.get("/diary/today").json()
    u2_list = user2_client.get("/diary/today").json()

    assert len(u1_list) == 1 and u1_list[0]["name"] == "U1 lunch"
    assert len(u2_list) == 1 and u2_list[0]["name"] == "U2 dinner"
