"""Tests for Pydantic schemas — valid AND invalid inputs."""

import pytest
from pydantic import ValidationError

from src.schemas.auth import LoginRequest, RegisterRequest
from src.schemas.tools import ClassifierInput, DestinationQuery, LiveConditionsInput


# ── DestinationQuery ──────────────────────────────────────────────────────────

def test_destination_query_valid():
    q = DestinationQuery(query="best hiking destination warm", k=3)
    assert q.k == 3
    assert q.destination is None


def test_destination_query_invalid_too_short():
    with pytest.raises(ValidationError) as exc:
        DestinationQuery(query="hi")
    assert "min_length" in str(exc.value).lower() or "string_too_short" in str(exc.value).lower()


def test_destination_query_invalid_k_too_large():
    with pytest.raises(ValidationError):
        DestinationQuery(query="good hiking", k=99)


def test_destination_query_with_destination():
    q = DestinationQuery(query="best activities", destination="Bali", k=4)
    assert q.destination == "Bali"


# ── ClassifierInput ───────────────────────────────────────────────────────────

VALID_FEATURES = {
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


def test_classifier_valid():
    c = ClassifierInput(**VALID_FEATURES)
    assert c.destination == "Bali"


def test_classifier_invalid_temp():
    with pytest.raises(ValidationError):
        ClassifierInput(**{**VALID_FEATURES, "avg_temp_july": 999})


def test_classifier_invalid_cost():
    with pytest.raises(ValidationError):
        ClassifierInput(**{**VALID_FEATURES, "cost_per_day_usd": -5})


def test_classifier_invalid_score():
    with pytest.raises(ValidationError):
        ClassifierInput(**{**VALID_FEATURES, "hiking_score": 11})


# ── LiveConditionsInput ───────────────────────────────────────────────────────

VALID_LIVE = {
    "destination": "Bali",
    "city": "Denpasar",
    "currency_code": "idr",  # lowercase → uppercased by validator
    "travel_month": 7,
    "origin_iata": "lhr",
    "destination_iata": "dps",
}


def test_live_conditions_valid():
    c = LiveConditionsInput(**VALID_LIVE)
    assert c.currency_code == "IDR"
    assert c.origin_iata == "LHR"
    assert c.destination_iata == "DPS"


def test_live_conditions_invalid_month():
    with pytest.raises(ValidationError):
        LiveConditionsInput(**{**VALID_LIVE, "travel_month": 13})


def test_live_conditions_invalid_iata():
    with pytest.raises(ValidationError):
        LiveConditionsInput(**{**VALID_LIVE, "origin_iata": "TOOLONG"})


# ── Auth schemas ──────────────────────────────────────────────────────────────

def test_register_valid():
    r = RegisterRequest(email="user@example.com", username="user123", password="securepass123")
    assert r.username == "user123"


def test_register_invalid_username():
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", username="user name!", password="pass12345")


def test_register_invalid_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", username="user", password="short")
