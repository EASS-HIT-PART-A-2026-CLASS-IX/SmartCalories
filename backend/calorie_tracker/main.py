from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .rate_limit import RateLimitMiddleware
from .routers import (
    account,
    auth_demo,
    chat,
    diary,
    health,
    insights,
    logs,
    photo,
    uploads,
    users,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_min)
    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(account.router)
    app.include_router(diary.router)
    app.include_router(insights.router)
    app.include_router(logs.router)
    app.include_router(chat.router)
    app.include_router(photo.router)
    app.include_router(auth_demo.router)
    app.include_router(uploads.router)
    return app


app = create_app()
