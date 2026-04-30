"""
Embedding service — wraps the OpenAI embeddings API.

Uses the async client from lifespan so we never create a new client per call.
text-embedding-3-small: 1536 dimensions, cheap ($0.02/1M tokens), good quality.
"""

from __future__ import annotations

import structlog

from src.core.config import settings
from src.core.lifespan import get_openai_client

logger = structlog.get_logger(__name__)


async def embed_text(text: str) -> list[float]:
    """Embed a single string. Returns a 1536-dim vector."""
    client = get_openai_client()
    response = await client.embeddings.create(
        input=text,
        model=settings.EMBEDDING_MODEL,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple strings in a single API call (up to 2048 inputs)."""
    if not texts:
        return []
    client = get_openai_client()
    response = await client.embeddings.create(
        input=texts,
        model=settings.EMBEDDING_MODEL,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
