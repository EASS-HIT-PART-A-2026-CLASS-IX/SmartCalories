from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from typing import Any

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from calorie_tracker import db as db_module
from calorie_tracker.auth import verify_firebase_token
from calorie_tracker.main import app


def _fake_verify_firebase_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Test stand-in. Token strings map to canned decoded payloads."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token == "expired" or token == "":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if token == "admin":
        return {"uid": "admin-uid", "email": "admin@example.com", "role": "admin"}
    if token == "anon":
        return {"uid": "anon-uid", "firebase": {"sign_in_provider": "anonymous"}, "role": "user"}
    if token == "user-2":
        return {"uid": "user-2-uid", "email": "u2@example.com", "role": "user"}
    return {"uid": "user-1-uid", "email": "u1@example.com", "role": "user"}


@pytest.fixture(autouse=True)
def _isolated_db_and_auth(monkeypatch):
    """Each test gets a fresh in-memory SQLite engine + a fake Firebase verifier."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(db_module, "_engine", engine, raising=False)
    app.dependency_overrides[db_module.get_session] = _override_session
    app.dependency_overrides[verify_firebase_token] = _fake_verify_firebase_token
    yield
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client() -> TestClient:
    """Default authenticated client (Bearer user-1)."""
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer user-1"})
    return c


@pytest.fixture
def admin_client() -> TestClient:
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer admin"})
    return c


@pytest.fixture
def anon_client() -> TestClient:
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer anon"})
    return c


@pytest.fixture
def user2_client() -> TestClient:
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer user-2"})
    return c


@pytest.fixture
def unauth_client() -> TestClient:
    """No Authorization header. Useful for 401 assertions."""
    return TestClient(app)
