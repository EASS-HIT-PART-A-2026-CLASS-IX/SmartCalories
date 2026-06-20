from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _now_iso(offset_hours: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()


def test_diary_create_today_lists_only_todays_entries(client: TestClient) -> None:
    r = client.post(
        "/diary",
        json={"name": "Coffee", "calories": 5, "meal": "breakfast", "protein_g": 0, "carb_g": 1, "fat_g": 0},
    )
    assert r.status_code == 201

    r = client.get("/diary/today")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Coffee"


def test_diary_patch_meal(client: TestClient) -> None:
    created = client.post(
        "/diary", json={"name": "Toast", "calories": 80, "meal": "breakfast"}
    ).json()
    eid = created["id"]
    r = client.patch(f"/diary/{eid}", json={"meal": "snack", "notes": "with butter"})
    assert r.status_code == 200
    assert r.json()["meal"] == "Snack"
    assert r.json()["notes"] == "with butter"


def test_insights_macros_today_aggregates(client: TestClient) -> None:
    client.post("/diary", json={"name": "A", "calories": 100, "protein_g": 5, "meal": "breakfast"})
    client.post("/diary", json={"name": "B", "calories": 200, "protein_g": 10, "meal": "lunch"})
    r = client.get("/insights/macros/today")
    assert r.status_code == 200
    body = r.json()
    assert body["calories"] == 300
    assert body["protein_g"] == 15.0


def test_insights_macros_range_returns_n_days(client: TestClient) -> None:
    r = client.get("/insights/macros/range?days=5")
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_insights_streak_zero_when_no_entries(client: TestClient) -> None:
    r = client.get("/insights/streak")
    assert r.status_code == 200
    assert r.json()["days"] == 0


def test_insights_streak_one_after_logging_today(client: TestClient) -> None:
    client.post("/diary", json={"name": "X", "calories": 1, "meal": "snack"})
    r = client.get("/insights/streak")
    assert r.json()["days"] == 1


def test_insights_tdee(client: TestClient) -> None:
    r = client.post(
        "/insights/tdee",
        json={"weight_kg": 80, "height_cm": 180, "age_years": 30, "sex": "male", "activity_level": "moderate"},
    )
    assert r.status_code == 200
    body = r.json()
    assert 1500 < body["bmr"] < 2200
    assert body["tdee"] > body["bmr"]
    assert body["suggested_macros"]["protein_g"] > 0
