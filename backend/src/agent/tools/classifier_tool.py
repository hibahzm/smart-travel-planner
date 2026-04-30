"""
ML classifier tool — predicts travel style using the trained scikit-learn pipeline.

The pipeline is loaded once in lifespan (not per-request). This tool wraps it
for use by the LangGraph agent via the tool allowlist.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import structlog
from langchain_core.tools import StructuredTool

from src.core.lifespan import get_ml_classifier, get_ml_label_encoder
from src.schemas.tools import ClassifierInput

logger = structlog.get_logger(__name__)

FEATURE_COLUMNS = [
    "avg_temp_july",
    "cost_per_day_usd",
    "crowd_index",
    "hiking_score",
    "beach_score",
    "cultural_sites",
    "safety_score",
    "english_score",
    "nature_score",
    "nightlife_score",
    "family_amenities",
    "luxury_hotels",
    "food_scene_score",
    "infrastructure_score",
    "wellness_score",
]


async def classify_destination_style(
    destination: str,
    avg_temp_july: float,
    cost_per_day_usd: float,
    crowd_index: float,
    hiking_score: float,
    beach_score: float,
    cultural_sites: int,
    safety_score: float,
    english_score: float,
    nature_score: float,
    nightlife_score: float,
    family_amenities: float,
    luxury_hotels: int,
    food_scene_score: float,
    infrastructure_score: float,
    wellness_score: float,
) -> str:
    """
    Classify a destination's travel style using the trained ML pipeline.

    Predicts one of: Adventure, Relaxation, Culture, Budget, Luxury, Family.
    Returns the predicted label with per-class probabilities.

    Args:
        destination: Destination name (for logging).
        avg_temp_july: Average July temperature in °C.
        cost_per_day_usd: Estimated daily budget in USD.
        crowd_index: Tourist crowd level 1–10.
        hiking_score: Trail quality and terrain variety 0–10.
        beach_score: Beach and water quality 0–10.
        cultural_sites: Count of UNESCO + major museums + historic districts.
        safety_score: Composite safety score 0–10.
        english_score: Ease of independent travel in English 0–10.
        nature_score: Wildlife, forests, national-park quality 0–10.
        nightlife_score: Bar/club/live-music scene 0–10.
        family_amenities: Kid-friendliness 0–10.
        luxury_hotels: Count of rated 5-star properties.
        food_scene_score: Cuisine diversity and fine-dining quality 0–10.
        infrastructure_score: Transport, internet, hospital access 0–10.
        wellness_score: Spas, yoga retreats, health tourism 0–10.
    """
    try:
        validated = ClassifierInput(
            destination=destination,
            avg_temp_july=avg_temp_july,
            cost_per_day_usd=cost_per_day_usd,
            crowd_index=crowd_index,
            hiking_score=hiking_score,
            beach_score=beach_score,
            cultural_sites=cultural_sites,
            safety_score=safety_score,
            english_score=english_score,
            nature_score=nature_score,
            nightlife_score=nightlife_score,
            family_amenities=family_amenities,
            luxury_hotels=luxury_hotels,
            food_scene_score=food_scene_score,
            infrastructure_score=infrastructure_score,
            wellness_score=wellness_score,
        )

        clf = get_ml_classifier()
        le = get_ml_label_encoder()

        features = np.array([[
            validated.avg_temp_july,
            validated.cost_per_day_usd,
            validated.crowd_index,
            validated.hiking_score,
            validated.beach_score,
            validated.cultural_sites,
            validated.safety_score,
            validated.english_score,
            validated.nature_score,
            validated.nightlife_score,
            validated.family_amenities,
            validated.luxury_hotels,
            validated.food_scene_score,
            validated.infrastructure_score,
            validated.wellness_score,
        ]])

        pred_encoded = clf.predict(features)[0]
        probas = clf.predict_proba(features)[0]
        label = le.inverse_transform([pred_encoded])[0]
        all_classes = {le.inverse_transform([i])[0]: round(float(p), 3) for i, p in enumerate(probas)}

        result = {
            "destination": validated.destination,
            "predicted_style": label,
            "confidence": round(float(max(probas)), 3),
            "all_probabilities": all_classes,
        }

        logger.info("classifier_tool", destination=validated.destination, style=label)
        return json.dumps(result)

    except RuntimeError as exc:
        # Model not loaded (training not run yet)
        return json.dumps({"error": str(exc), "destination": destination})
    except Exception as exc:
        logger.error("classifier_tool_error", error=str(exc))
        return json.dumps({"error": str(exc)})


def make_classifier_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=classify_destination_style,
        name="classify_destination_style",
        description=(
            "Classify a destination's travel style (Adventure/Relaxation/Culture/Budget/Luxury/Family) "
            "using the trained ML model. Supply numeric destination features."
        ),
        args_schema=ClassifierInput,
    )
