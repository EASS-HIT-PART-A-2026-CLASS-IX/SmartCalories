from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from .config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        kwargs: dict[str, object] = {"pool_pre_ping": True}
        if settings.database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def reset_engine() -> None:
    """Test helper to drop the cached engine after overriding settings."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def init_db() -> None:
    """Create tables for first-run dev/test environments — **SQLite only**.

    Postgres (Neon) schema is owned exclusively by Alembic. Running `create_all` there races the
    `alembic upgrade head` step in the compose command and creates tables out-of-band, which then
    makes a later migration fail with `DuplicateTable` (this happened with `user_llm_key`). So on
    Postgres this is a no-op and migrations are the single source of truth.
    """
    if get_settings().database_url.startswith("sqlite"):
        SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
