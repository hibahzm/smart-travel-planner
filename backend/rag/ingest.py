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
    # Original 12 (already in DB)
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
    # New 18 (need ingestion)
    "tokyo": "Tokyo, Japan",
    "dubai": "Dubai, UAE",
    "paris": "Paris, France",
    "rome": "Rome, Italy",
    "thailand_bangkok": "Bangkok, Thailand",
    "costa_rica": "Costa Rica",
    "istanbul": "Istanbul, Turkey",
    "singapore": "Singapore",
    "maldives": "Maldives",
    "rajasthan": "Rajasthan, India",
    "jordan": "Jordan",
    "zanzibar": "Zanzibar, Tanzania",
    "barcelona": "Barcelona, Spain",
    "argentina_buenos_aires": "Buenos Aires, Argentina",
    "switzerland": "Switzerland",
    "south_africa": "South Africa",
    "sri_lanka": "Sri Lanka",
    "mexico": "Mexico",
}

# Stems already ingested in the database — skip when running with --new-only
ALREADY_INGESTED = {
    "bali", "kyoto", "patagonia", "iceland", "morocco",
    "vietnam", "peru", "portugal", "georgia", "kenya",
    "colombia", "new_zealand",
}


async def main():
    import sys as _sys
    import src.core.lifespan as ls

    new_only = "--new-only" in _sys.argv

    await create_engine()

    ls._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    session_factory = get_session_factory()

    docs = []
    skipped = 0
    for txt_file in sorted(DOCUMENTS_DIR.glob("*.txt")):
        stem = txt_file.stem.lower()
        if new_only and stem in ALREADY_INGESTED:
            skipped += 1
            continue
        destination = DESTINATION_MAP.get(stem, stem.replace("_", " ").title())
        content = txt_file.read_text(encoding="utf-8")
        docs.append(RawDocument(
            destination=destination,
            source=f"Wikivoyage/{destination}",
            content=content,
        ))
        logger.info("loaded_document", destination=destination, chars=len(content))

    if new_only:
        logger.info("new_only_mode", skipped=skipped)

    logger.info("starting_ingest", documents=len(docs))
    async with session_factory() as db:
        total = await ingest_documents(docs, db)

    logger.info("ingest_complete", total_chunks=total)
    await ls._openai_client.close()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
