"""
RAG ingestion service — chunks documents and stores embeddings in pgvector.

Chunking strategy (defended):
  - tiktoken for token-accurate splitting (not character-based).
  - Chunk size: 512 tokens — captures a full Wikivoyage sub-section.
  - Overlap: 64 tokens — preserves linking sentences at chunk boundaries.
  - Section-aware: split on '##' headers first, then by size within sections.
    This keeps semantically coherent content together.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

import structlog
import tiktoken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.document_chunk import DocumentChunk
from src.services.embeddings import embed_batch

logger = structlog.get_logger(__name__)

_tokenizer = tiktoken.get_encoding("cl100k_base")


@dataclass
class RawDocument:
    destination: str
    source: str
    content: str


def _tokenize(text: str) -> list[int]:
    return _tokenizer.encode(text)


def _decode(tokens: list[int]) -> str:
    return _tokenizer.decode(tokens)


def chunk_document(doc: RawDocument) -> list[dict]:
    """
    Chunk a document into overlapping token windows.

    Strategy:
    1. Split on '##' section headers to preserve semantic sections.
    2. If a section exceeds CHUNK_SIZE, split further by token window.
    3. Apply CHUNK_OVERLAP tokens of look-back between consecutive chunks.
    """
    chunk_size = settings.RAG_CHUNK_SIZE
    overlap = settings.RAG_CHUNK_OVERLAP

    # Split on section headers while keeping the header with the section
    sections = re.split(r"(?=^##\s)", doc.content, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    chunks = []
    chunk_index = 0

    for section in sections:
        tokens = _tokenize(section)

        if len(tokens) <= chunk_size:
            # Section fits in one chunk — keep it whole
            chunks.append({
                "destination": doc.destination,
                "source": doc.source,
                "content": section,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
        else:
            # Section too large — sliding window
            start = 0
            while start < len(tokens):
                end = min(start + chunk_size, len(tokens))
                chunk_tokens = tokens[start:end]
                chunks.append({
                    "destination": doc.destination,
                    "source": doc.source,
                    "content": _decode(chunk_tokens),
                    "chunk_index": chunk_index,
                })
                chunk_index += 1
                start += chunk_size - overlap  # slide forward, keep overlap

    return chunks


async def ingest_documents(docs: list[RawDocument], db: AsyncSession) -> int:
    """Chunk all documents, embed in batches, and upsert into pgvector."""
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))

    logger.info("ingesting", total_chunks=len(all_chunks))

    # Embed in batches of 100 (API limit is 2048 but 100 keeps memory low)
    batch_size = 100
    all_embeddings = []
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = await embed_batch(texts)
        all_embeddings.extend(embeddings)
        logger.info("embedded_batch", batch=i // batch_size + 1)

    # Upsert rows
    for chunk, embedding in zip(all_chunks, all_embeddings):
        row = DocumentChunk(
            destination=chunk["destination"],
            source=chunk["source"],
            content=chunk["content"],
            chunk_index=chunk["chunk_index"],
            embedding=embedding,
        )
        db.add(row)

    await db.commit()
    logger.info("ingest_complete", total=len(all_chunks))
    return len(all_chunks)
