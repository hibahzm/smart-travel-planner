"""
Single source of truth for all configuration.

All values come from environment variables (validated at startup via pydantic-settings).
If a required key is missing the app refuses to start — not a silent failure.
No os.getenv() calls elsewhere in the codebase; import `settings` from here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(..., description="Async SQLAlchemy DSN (asyncpg)")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    PLANNER_MODEL: str = Field(default="gpt-4o-mini", description="Cheap model for tool routing")
    SYNTHESIZER_MODEL: str = Field(default="gpt-4o", description="Strong model for final synthesis")

    # ── External APIs ──────────────────────────────────────────────────────────
    OPENWEATHERMAP_API_KEY: str = Field(..., description="OpenWeatherMap API key")

    # ── Auth ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., min_length=32, description="JWT signing secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ── Webhook ────────────────────────────────────────────────────────────────
    DISCORD_WEBHOOK_URL: str | None = Field(default=None)
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 3

    # ── LangSmith ─────────────────────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str = "smart-travel-planner"

    # ── App ────────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── ML ────────────────────────────────────────────────────────────────────
    ML_MODEL_PATH: str = "ml/models/classifier.joblib"
    ML_ENCODER_PATH: str = "ml/models/label_encoder.joblib"

    # ── RAG ───────────────────────────────────────────────────────────────────
    # Chunk size: 512 tokens captures a full Wikivoyage sub-section (e.g. "Do",
    # "See") without splitting mid-thought. Tested against 256 (too granular,
    # splits activity descriptions) and 1024 (too broad, returns irrelevant content).
    RAG_CHUNK_SIZE: int = 512
    # 64-token overlap preserves sentence continuity at chunk boundaries.
    # Travel content has linking sentences ("From here you can...") that must
    # appear in both adjacent chunks.
    RAG_CHUNK_OVERLAP: int = 64
    # k=4 returns enough context for synthesis without flooding the LLM.
    # k=3 sometimes missed budget info; k=5 returned duplicates in testing.
    RAG_TOP_K: int = 4
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — loads once, reused for the process lifetime."""
    return Settings()


settings: Settings = get_settings()
