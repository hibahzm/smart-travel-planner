"""
Pydantic schemas that guard every tool input.

The agent (LLM) sends JSON; these schemas validate it before the function runs.
If the LLM sends garbage, validation raises ValidationError and the agent
receives a structured error message — it retries rather than crashing.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── RAG Tool ──────────────────────────────────────────────────────────────────

class DestinationQuery(BaseModel):
    """Input for the knowledge-retrieval (RAG) tool."""

    query: str = Field(
        min_length=3,
        max_length=500,
        description="Natural-language question about a destination",
    )
    destination: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional: narrow results to a specific destination",
    )
    k: int = Field(default=4, ge=1, le=10, description="Number of chunks to retrieve")


# ── Classifier Tool ───────────────────────────────────────────────────────────

class ClassifierInput(BaseModel):
    """
    Input for the ML-classifier tool.

    Features are the same numeric columns the model was trained on.
    The agent must supply realistic estimates; the model returns the
    predicted travel style with confidence.
    """

    destination: str = Field(min_length=2, max_length=100)
    avg_temp_july: float = Field(ge=-30, le=50, description="Average July temp °C")
    cost_per_day_usd: float = Field(ge=0, le=2000, description="Estimated daily budget in USD")
    crowd_index: float = Field(ge=1, le=10, description="Tourist crowd level (1=empty, 10=overrun)")
    hiking_score: float = Field(ge=0, le=10)
    beach_score: float = Field(ge=0, le=10)
    cultural_sites: int = Field(ge=0, le=30, description="Count of major cultural sites")
    safety_score: float = Field(ge=0, le=10)
    english_score: float = Field(ge=0, le=10)
    nature_score: float = Field(ge=0, le=10)
    nightlife_score: float = Field(ge=0, le=10)
    family_amenities: float = Field(ge=0, le=10)
    luxury_hotels: int = Field(ge=0, le=50, description="Count of 5-star hotels")


# ── Live Conditions Tool ──────────────────────────────────────────────────────

class LiveConditionsInput(BaseModel):
    """Input for the live-conditions tool (weather + FX + flights)."""

    destination: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100, description="City name for weather lookup")
    currency_code: str = Field(
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code of destination (e.g. IDR, JPY)",
    )
    travel_month: int = Field(ge=1, le=12, description="Month of travel (1–12)")
    origin_iata: str = Field(
        min_length=3,
        max_length=3,
        description="IATA code of departure airport (e.g. JFK, LHR)",
    )
    destination_iata: str = Field(
        min_length=3,
        max_length=3,
        description="IATA code of destination airport (e.g. DPS, KIX)",
    )

    @field_validator("currency_code", "origin_iata", "destination_iata", mode="before")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()
