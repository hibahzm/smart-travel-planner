"""Async SQLAlchemy engine singleton — created once in lifespan."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import settings

_engine: AsyncEngine | None = None


async def create_engine() -> AsyncEngine:
    global _engine
    _engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "development",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialised")
    return _engine
