from fastapi.testclient import TestClient


def test_list_empty(client: TestClient) -> None:
    r = client.get("/entries")
    assert r.status_code == 200
    assert r.json() == []


def test_create_list_get(client: TestClient) -> None:
    create = client.post(
        "/entries",
        json={"name": "Oatmeal", "calories": 150, "meal": "breakfast"},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Oatmeal"
    assert body["calories"] == 150
    assert body["meal"] == "Breakfast"
    eid = body["id"]

    listed = client.get("/entries")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = client.get(f"/entries/{eid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Oatmeal"


def test_update(client: TestClient) -> None:
    client.post(
        "/entries",
        json={"name": "Salad", "calories": 200, "meal": "lunch"},
    )
    r = client.put(
        "/entries/1",
        json={"name": "Big salad", "calories": 350, "meal": "lunch"},
    )
    assert r.status_code == 200
    assert r.json() == {
        "id": 1,
        "name": "Big salad",
        "calories": 350,
        "meal": "Lunch",
    }


def test_delete(client: TestClient) -> None:
    client.post(
        "/entries",
        json={"name": "Snack", "calories": 80, "meal": "snack"},
    )
    d = client.delete("/entries/1")
    assert d.status_code == 204
    assert client.get("/entries/1").status_code == 404


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
