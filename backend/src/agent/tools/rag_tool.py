"""
RAG retrieval tool — fetches destination knowledge from pgvector.

Chunking rationale (see also config.py and README):
  - 512-token chunks: captures a full Wikivoyage sub-section (e.g. "Do", "See")
    without splitting mid-thought. Tested 256 (too granular) and 1024 (too broad).
  - 64-token overlap: preserves linking sentences at chunk boundaries.
  - k=4 default: enough context for synthesis; k=5 returned duplicates in testing.
  - Similarity threshold implicit in ORDER BY + LIMIT — no hard cutoff because
    pgvector cosine distance ranking is reliable for this content type.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.tools import StructuredTool
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.document_chunk import DocumentChunk
from src.schemas.tools import DestinationQuery
from src.services.embeddings import embed_text

logger = structlog.get_logger(__name__)


async def _retrieve(
    query: str,
    destination: str | None = None,
    k: int = 4,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Core retrieval logic — separated so the tool wrapper can inject the DB session."""
    start = time.perf_counter()

    if db is None:
        return {"error": "Database session not available"}

    try:
        embedding = await embed_text(query)
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # pgvector cosine distance — lower is more similar
        if destination:
            stmt = text(
                """
                SELECT id, destination, source, content, chunk_index,
                       1 - (embedding <=> CAST(:emb AS vector)) AS similarity
                FROM document_chunks
                WHERE destination ILIKE :dest
                ORDER BY embedding <=> CAST(:emb AS vector)
                LIMIT :k
                """
            ).bindparams(emb=embedding_str, dest=f"%{destination}%", k=k)
        else:
            stmt = text(
                """
                SELECT id, destination, source, content, chunk_index,
                       1 - (embedding <=> CAST(:emb AS vector)) AS similarity
                FROM document_chunks
                ORDER BY embedding <=> CAST(:emb AS vector)
                LIMIT :k
                """
            ).bindparams(emb=embedding_str, k=k)

        result = await db.execute(stmt)
        rows = result.fetchall()

        chunks = [
            {
                "destination": r.destination,
                "source": r.source,
                "content": r.content,
                "chunk_index": r.chunk_index,
                "similarity": round(float(r.similarity), 4),
            }
            for r in rows
        ]

        duration = int((time.perf_counter() - start) * 1000)
        logger.info("rag_retrieval", query=query[:80], k=k, chunks_found=len(chunks), duration_ms=duration)

        return {
            "query": query,
            "chunks": chunks,
            "total_found": len(chunks),
        }

    except Exception as exc:
        logger.error("rag_retrieval_error", error=str(exc))
        return {"error": str(exc), "query": query, "chunks": []}


def make_rag_tool(db: AsyncSession) -> StructuredTool:
    """Factory — injects the db session so the tool doesn't hold a global."""

    async def retrieve_destination_knowledge(
        query: str,
        destination: str | None = None,
        k: int = 4,
    ) -> str:
        """
        Search the destination knowledge base for relevant travel information.

        Use this tool to retrieve facts about activities, climate, costs, culture,
        and practical travel tips for one or more destinations.

        Args:
            query: Natural-language question about a destination.
            destination: Optional destination name to narrow results.
            k: Number of chunks to return (default 4).

        Returns:
            JSON string with retrieved chunks and similarity scores.
        """
        validated = DestinationQuery(query=query, destination=destination, k=k)
        result = await _retrieve(
            query=validated.query,
            destination=validated.destination,
            k=validated.k,
            db=db,
        )
        return json.dumps(result, ensure_ascii=False)

    return StructuredTool.from_function(
        coroutine=retrieve_destination_knowledge,
        name="retrieve_destination_knowledge",
        description=(
            "Search the destination knowledge base for travel information. "
            "Returns relevant text chunks about activities, climate, costs, culture, and tips."
        ),
        args_schema=DestinationQuery,
    )
