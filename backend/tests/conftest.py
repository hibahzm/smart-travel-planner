"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.models.base import Base
from src.models.user import User


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_openai_client():
    """Returns a mock AsyncOpenAI client that returns a canned embedding."""
    client = AsyncMock()
    embedding_response = MagicMock()
    embedding_response.data = [MagicMock(embedding=[0.1] * 1536, index=0)]
    client.embeddings.create = AsyncMock(return_value=embedding_response)
    return client


@pytest.fixture
def mock_user():
    user = User()
    user.id = __import__("uuid").uuid4()
    user.email = "test@example.com"
    user.username = "testuser"
    user.hashed_password = "hashed"
    user.webhook_url = None
    return user


@pytest.fixture
async def app(mock_user) -> FastAPI:
    """App with DB and auth dependencies overridden."""
    from src.main import app as _app

    # Override auth
    _app.dependency_overrides[get_current_user] = lambda: mock_user

    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
