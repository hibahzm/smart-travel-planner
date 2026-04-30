"""
RAG ingestion script.

Run after starting the database:
  docker compose up db -d
  uv run python rag/ingest.py

Reads all .txt files from rag/documents/, chunks them with the strategy
documented in src/services/rag.py and config.py, embeds via OpenAI, and
stores in the pgvector table.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make src importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.core.config import settings
from src.core.lifespan import _openai_client
from src.db.engine import create_engine, dispose_engine
from src.db.session import get_session_factory
from src.services.rag import RawDocument, ingest_documents

import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)

DOCUMENTS_DIR = Path(__file__).parent / "documents"

DESTINATION_MAP = {
    "bali": "Bali, Indonesia",
    "kyoto": "Kyoto, Japan",
    "patagonia": "Patagonia",
    "iceland": "Iceland",
    "morocco": "Morocco",
    "vietnam": "Vietnam",
    "peru": "Peru",
    "portugal": "Portugal",
    "georgia": "Georgia",
    "kenya": "Kenya",
    "colombia": "Colombia",
    "new_zealand": "New Zealand",
}


async def main():
    import src.core.lifespan as ls

    await create_engine()

    # Manually init the OpenAI client (normally done in lifespan)
    ls._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    session_factory = get_session_factory()

    docs = []
    for txt_file in sorted(DOCUMENTS_DIR.glob("*.txt")):
        stem = txt_file.stem.lower()
        destination = DESTINATION_MAP.get(stem, stem.replace("_", " ").title())
        content = txt_file.read_text(encoding="utf-8")
        docs.append(RawDocument(
            destination=destination,
            source=f"Wikivoyage/{destination}",
            content=content,
        ))
        logger.info("loaded_document", destination=destination, chars=len(content))

    logger.info("starting_ingest", documents=len(docs))
    async with session_factory() as db:
        total = await ingest_documents(docs, db)

    logger.info("ingest_complete", total_chunks=total)
    await ls._openai_client.close()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
