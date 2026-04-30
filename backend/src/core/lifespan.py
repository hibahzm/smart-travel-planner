"""
FastAPI lifespan handler.

Creates every singleton exactly once on startup and disposes it on shutdown.
Everything that should exist once per process lives here:
  - async DB engine
  - OpenAI async client
  - Embedding model client
  - Loaded ML joblib model (loaded once, never on every request)
  - pgvector/RAG connection
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import logging
from fastapi import FastAPI
from openai import AsyncOpenAI

from src.core.config import settings
from src.db.engine import create_engine, dispose_engine

logger = logging.getLogger(__name__)

# Module-level holders — set in lifespan, read via get_* dependencies
_openai_client: AsyncOpenAI | None = None
_ml_classifier = None
_ml_label_encoder = None


def get_openai_client() -> AsyncOpenAI:
    if _openai_client is None:
        raise RuntimeError("OpenAI client not initialised — lifespan not run")
    return _openai_client


def get_ml_classifier():
    if _ml_classifier is None:
        raise RuntimeError("ML model not loaded — run `make train` first")
    return _ml_classifier


def get_ml_label_encoder():
    if _ml_label_encoder is None:
        raise RuntimeError("Label encoder not loaded — run `make train` first")
    return _ml_label_encoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _openai_client, _ml_classifier, _ml_label_encoder

    logger.info("startup: initialising singletons")

    # 0. LangSmith — propagate to os.environ so LangChain SDK picks it up
    #    (Pydantic-settings parses .env but does NOT write back to os.environ)
    if settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info("startup: langsmith tracing enabled", project=settings.LANGCHAIN_PROJECT)
    else:
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        logger.info("startup: langsmith tracing disabled (no API key)")

    # 1. Database engine
    await create_engine()
    logger.info("startup: db engine ready")

    # 2. OpenAI async client (one per process, reuses connection pool)
    _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("startup: openai client ready")

    # 3. ML model — loaded once; loading on every request is a bug, not a style choice
    model_path = Path(settings.ML_MODEL_PATH)
    encoder_path = Path(settings.ML_ENCODER_PATH)
    if model_path.exists() and encoder_path.exists():
        _ml_classifier = joblib.load(model_path)
        _ml_label_encoder = joblib.load(encoder_path)
        logger.info("startup: ml model loaded", path=str(model_path))
    else:
        logger.warning("startup: ml model not found — classify tool will be unavailable", path=str(model_path))

    logger.info("startup: all singletons ready")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("shutdown: disposing resources")
    await dispose_engine()
    if _openai_client:
        await _openai_client.close()
    logger.info("shutdown: done")
