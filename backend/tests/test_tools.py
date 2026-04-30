"""Tests for each tool in isolation — no real LLM calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.tools.classifier_tool import classify_destination_style
from src.agent.tools.live_conditions_tool import fetch_live_conditions


# ── Classifier Tool ───────────────────────────────────────────────────────────

class TestClassifierTool:
    VALID_ARGS = {
        "destination": "Bali",
        "avg_temp_july": 26.0,
        "cost_per_day_usd": 60.0,
        "crowd_index": 6.0,
        "hiking_score": 5.0,
        "beach_score": 8.0,
        "cultural_sites": 4,
        "safety_score": 7.0,
        "english_score": 7.0,
        "nature_score": 8.0,
        "nightlife_score": 5.0,
        "family_amenities": 6.0,
        "luxury_hotels": 4,
    }

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        mock_clf = MagicMock()
        mock_clf.predict.return_value = [1]
        mock_clf.predict_proba.return_value = [[0.1, 0.6, 0.1, 0.1, 0.05, 0.05]]

        mock_le = MagicMock()
        mock_le.inverse_transform.side_effect = lambda x: ["Relaxation"]
        mock_le.classes_ = ["Adventure", "Budget", "Culture", "Family", "Luxury", "Relaxation"]

        with patch("src.agent.tools.classifier_tool.get_ml_classifier", return_value=mock_clf), \
             patch("src.agent.tools.classifier_tool.get_ml_label_encoder", return_value=mock_le):
            result = await classify_destination_style(**self.VALID_ARGS)

        data = json.loads(result)
        assert "predicted_style" in data
        assert "confidence" in data
        assert "all_probabilities" in data

    @pytest.mark.asyncio
    async def test_returns_error_when_model_not_loaded(self):
        with patch("src.agent.tools.classifier_tool.get_ml_classifier",
                   side_effect=RuntimeError("Model not loaded")):
            result = await classify_destination_style(**self.VALID_ARGS)

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_validation_rejects_invalid_input(self):
        bad_args = {**self.VALID_ARGS, "hiking_score": 99.0}
        result = await classify_destination_style(**bad_args)
        data = json.loads(result)
        assert "error" in data


# ── Live Conditions Tool ──────────────────────────────────────────────────────

class TestLiveConditionsTool:
    VALID_ARGS = {
        "destination": "Bali",
        "city": "Denpasar",
        "currency_code": "IDR",
        "travel_month": 7,
        "origin_iata": "LHR",
        "destination_iata": "DPS",
    }

    @pytest.mark.asyncio
    async def test_returns_valid_json_on_success(self):
        mock_weather = {
            "city": "Denpasar", "temp_c": 27.0, "description": "clear sky",
            "humidity_pct": 70, "wind_speed_ms": 3.5, "feels_like_c": 29.0, "country": "ID"
        }
        mock_fx = {"base": "USD", "target": "IDR", "rate": 15600, "meaning": "1 USD = 15600 IDR"}
        mock_flights = {"available": True, "cheapest_usd": 450.0, "average_usd": 520.0}

        with patch("src.agent.tools.live_conditions_tool._fetch_weather",
                   new_callable=AsyncMock, return_value=mock_weather), \
             patch("src.agent.tools.live_conditions_tool._fetch_fx",
                   new_callable=AsyncMock, return_value=mock_fx), \
             patch("src.agent.tools.live_conditions_tool._fetch_flights",
                   new_callable=AsyncMock, return_value=mock_flights):
            result = await fetch_live_conditions(**self.VALID_ARGS)

        data = json.loads(result)
        assert "weather" in data
        assert "exchange_rate" in data
        assert "flights" in data
        assert data["weather"]["temp_c"] == 27.0

    @pytest.mark.asyncio
    async def test_weather_failure_does_not_kill_fx(self):
        """A weather API outage must not prevent FX data from returning."""
        mock_fx = {"base": "USD", "target": "IDR", "rate": 15600}
        mock_flights = {"available": False}

        with patch("src.agent.tools.live_conditions_tool._fetch_weather",
                   new_callable=AsyncMock, side_effect=Exception("API timeout")), \
             patch("src.agent.tools.live_conditions_tool._fetch_fx",
                   new_callable=AsyncMock, return_value=mock_fx), \
             patch("src.agent.tools.live_conditions_tool._fetch_flights",
                   new_callable=AsyncMock, return_value=mock_flights):
            result = await fetch_live_conditions(**self.VALID_ARGS)

        data = json.loads(result)
        assert "error" in data["weather"]
        assert data["exchange_rate"]["rate"] == 15600  # FX still returned

    @pytest.mark.asyncio
    async def test_invalid_input_returns_error(self):
        bad_args = {**self.VALID_ARGS, "travel_month": 13}
        result = await fetch_live_conditions(**bad_args)
        data = json.loads(result)
        assert "error" in data
