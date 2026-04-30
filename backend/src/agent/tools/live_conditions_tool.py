"""
Live conditions tool — fetches real-time weather, exchange rates, and flight estimates.

APIs used:
  - OpenWeatherMap Current Weather API (free tier, 60 req/min)
  - Frankfurter API for FX (https://api.frankfurter.app — free, no key)
  - Distance-based flight cost estimator (no external API — always reliable)

Retries: tenacity with exponential backoff on transient failures.
Caching: weather for same city within 10 minutes returns cached result.
Failure isolation: each sub-call is independent; a failure in one does NOT
  kill the others.
"""

from __future__ import annotations

import json
import math
from typing import Any

import httpx
import structlog
from cachetools import TTLCache
from langchain_core.tools import StructuredTool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.schemas.tools import LiveConditionsInput

logger = structlog.get_logger(__name__)

_weather_cache: TTLCache = TTLCache(maxsize=128, ttl=600)
_fx_cache: TTLCache = TTLCache(maxsize=64, ttl=3600)

# (lat, lon) for major airports — covers project destinations + common departure hubs
_AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    # Project destinations
    "DPS": (-8.749, 115.167),   # Bali
    "NBO": (-1.319, 36.928),    # Nairobi / Kenya
    "LIS": (38.774, -9.134),    # Lisbon
    "BOG": (4.701, -74.147),    # Bogota
    "KIX": (34.427, 135.244),   # Osaka Kansai (Kyoto)
    "ITM": (34.785, 135.438),   # Osaka Itami
    "HAN": (21.221, 105.807),   # Hanoi
    "SGN": (10.819, 106.652),   # Ho Chi Minh City
    "DAD": (16.044, 108.199),   # Da Nang
    "RAK": (31.606, -8.036),    # Marrakesh
    "CMN": (33.368, -7.590),    # Casablanca
    "KEF": (63.985, -22.606),   # Reykjavik
    "TBS": (41.669, 44.955),    # Tbilisi
    "ZQN": (-45.021, 168.739),  # Queenstown NZ
    "CHC": (-43.489, 172.532),  # Christchurch NZ
    "AKL": (-37.008, 174.791),  # Auckland
    "SCL": (-33.393, -70.786),  # Santiago (near Patagonia)
    "PMC": (-41.438, -73.095),  # Puerto Montt (Patagonia)
    "LIM": (-12.022, -77.114),  # Lima
    "CUZ": (-13.535, -71.939),  # Cusco (Machu Picchu)
    # Common departure hubs
    "LHR": (51.477, -0.461),    # London Heathrow
    "LGW": (51.156, -0.179),    # London Gatwick
    "STN": (51.885, 0.235),     # London Stansted
    "CDG": (49.009, 2.548),     # Paris CDG
    "ORY": (48.726, 2.365),     # Paris Orly
    "AMS": (52.310, 4.768),     # Amsterdam
    "FRA": (50.033, 8.570),     # Frankfurt
    "MUC": (48.354, 11.786),    # Munich
    "MAD": (40.472, -3.561),    # Madrid
    "BCN": (41.297, 2.078),     # Barcelona
    "FCO": (41.800, 12.239),    # Rome Fiumicino
    "MXP": (45.630, 8.723),     # Milan Malpensa
    "ZRH": (47.458, 8.548),     # Zurich
    "VIE": (48.110, 16.571),    # Vienna
    "BRU": (50.901, 4.484),     # Brussels
    "CPH": (55.618, 12.656),    # Copenhagen
    "ARN": (59.651, 17.919),    # Stockholm
    "OSL": (60.194, 11.100),    # Oslo
    "HEL": (60.317, 24.963),    # Helsinki
    "JFK": (40.641, -73.779),   # New York JFK
    "EWR": (40.690, -74.175),   # Newark
    "BOS": (42.366, -71.010),   # Boston
    "LAX": (33.943, -118.408),  # Los Angeles
    "SFO": (37.619, -122.374),  # San Francisco
    "ORD": (41.974, -87.908),   # Chicago O'Hare
    "DFW": (32.897, -97.038),   # Dallas
    "MIA": (25.796, -80.287),   # Miami
    "ATL": (33.641, -84.427),   # Atlanta
    "YYZ": (43.678, -79.631),   # Toronto
    "YVR": (49.195, -123.184),  # Vancouver
    "MEX": (19.436, -99.072),   # Mexico City
    "GRU": (-23.432, -46.470),  # Sao Paulo
    "EZE": (-34.822, -58.536),  # Buenos Aires
    "BOG": (4.701, -74.147),    # Bogota El Dorado
    "DXB": (25.253, 55.364),    # Dubai
    "AUH": (24.433, 54.651),    # Abu Dhabi
    "DOH": (25.274, 51.608),    # Doha
    "IST": (41.275, 28.752),    # Istanbul
    "CAI": (30.122, 31.406),    # Cairo
    "JNB": (-26.134, 28.242),   # Johannesburg
    "CPT": (-33.965, 18.602),   # Cape Town
    "SIN": (1.350, 103.994),    # Singapore Changi
    "BKK": (13.681, 100.747),   # Bangkok Suvarnabhumi
    "KUL": (2.745, 101.710),    # Kuala Lumpur
    "CGK": (-6.125, 106.655),   # Jakarta
    "MNL": (14.509, 121.020),   # Manila
    "NRT": (35.765, 140.386),   # Tokyo Narita
    "HND": (35.552, 139.781),   # Tokyo Haneda
    "ICN": (37.460, 126.441),   # Seoul Incheon
    "PEK": (40.080, 116.584),   # Beijing Capital
    "PVG": (31.143, 121.805),   # Shanghai Pudong
    "DEL": (28.556, 77.100),    # Delhi
    "BOM": (19.089, 72.868),    # Mumbai
    "SYD": (-33.947, 151.177),  # Sydney
    "MEL": (-37.673, 144.843),  # Melbourne
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _price_range(distance_km: float) -> tuple[float, float]:
    """Return (cheapest, average) USD estimate based on great-circle distance."""
    if distance_km < 1500:
        return (80.0, 200.0)
    elif distance_km < 3000:
        return (150.0, 380.0)
    elif distance_km < 6000:
        return (350.0, 680.0)
    elif distance_km < 10000:
        return (550.0, 980.0)
    else:
        return (750.0, 1350.0)


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _fetch_weather(city: str, client: httpx.AsyncClient) -> dict[str, Any]:
    if city in _weather_cache:
        logger.debug("weather_cache_hit", city=city)
        return _weather_cache[city]

    resp = await client.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": city, "appid": settings.OPENWEATHERMAP_API_KEY, "units": "metric"},
        timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()

    result = {
        "city": data.get("name", city),
        "country": data.get("sys", {}).get("country", ""),
        "temp_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity_pct": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "wind_speed_ms": data["wind"]["speed"],
    }
    _weather_cache[city] = result
    return result


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _fetch_fx(currency_code: str, client: httpx.AsyncClient) -> dict[str, Any]:
    if currency_code in _fx_cache:
        logger.debug("fx_cache_hit", currency=currency_code)
        return _fx_cache[currency_code]

    try:
        resp = await client.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"from": "USD", "to": currency_code},
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.debug("fx_unsupported_currency", currency=currency_code)
            return {
                "base": "USD",
                "target": currency_code,
                "rate": None,
                "date": None,
                "meaning": f"{currency_code} not supported by exchange rate provider (ECB-sourced data only)",
            }
        raise

    data = resp.json()
    rate = data["rates"].get(currency_code)
    result = {
        "base": "USD",
        "target": currency_code,
        "rate": rate,
        "date": data.get("date"),
        "meaning": f"1 USD = {rate} {currency_code}" if rate else "Rate unavailable",
    }
    _fx_cache[currency_code] = result
    return result


async def _fetch_flights(
    origin: str, destination: str, travel_month: int, client: httpx.AsyncClient
) -> dict[str, Any]:
    """
    Estimate flight costs using great-circle distance between airports.

    No external API needed — the Amadeus self-service tier was shut down in 2026
    and no equivalent free pricing API exists. Distance-based estimates are
    comparable in accuracy to the synthetic test data Amadeus returned anyway.
    """
    origin_coords = _AIRPORT_COORDS.get(origin.upper())
    dest_coords = _AIRPORT_COORDS.get(destination.upper())

    if not origin_coords or not dest_coords:
        unknown = [c for c, coords in [(origin, origin_coords), (destination, dest_coords)] if not coords]
        return {
            "available": False,
            "note": f"Airport(s) not in local database: {', '.join(unknown)}. Add coordinates to _AIRPORT_COORDS.",
        }

    distance_km = _haversine_km(*origin_coords, *dest_coords)
    cheapest, average = _price_range(distance_km)

    skyscanner_url = (
        f"https://www.skyscanner.net/transport/flights"
        f"/{origin.lower()}/{destination.lower()}/"
    )
    google_flights_url = (
        f"https://www.google.com/travel/flights/search"
        f"?q=flights+from+{origin}+to+{destination}"
    )

    return {
        "available": True,
        "route": f"{origin} → {destination}",
        "distance_km": round(distance_km),
        "cheapest_usd": cheapest,
        "average_usd": average,
        "book_skyscanner": skyscanner_url,
        "book_google_flights": google_flights_url,
        "note": (
            f"Price estimate based on flight distance. "
            f"Check live fares on Skyscanner: {skyscanner_url}"
        ),
    }


async def fetch_live_conditions(
    destination: str,
    city: str,
    currency_code: str,
    travel_month: int,
    origin_iata: str,
    destination_iata: str,
) -> str:
    """
    Fetch current weather, live exchange rates, and flight estimates for a destination.

    Args:
        destination: Full destination name.
        city: City name for weather API.
        currency_code: ISO 4217 code of destination currency (e.g. IDR, JPY).
        travel_month: Month of intended travel (1–12).
        origin_iata: Departure airport IATA code.
        destination_iata: Destination airport IATA code.
    """
    try:
        validated = LiveConditionsInput(
            destination=destination,
            city=city,
            currency_code=currency_code,
            travel_month=travel_month,
            origin_iata=origin_iata,
            destination_iata=destination_iata,
        )
    except Exception as exc:
        return json.dumps({"error": f"Invalid input: {exc}"})

    results: dict[str, Any] = {"destination": validated.destination}

    async with httpx.AsyncClient() as client:
        try:
            results["weather"] = await _fetch_weather(validated.city, client)
        except Exception as exc:
            logger.error("weather_failed", city=validated.city, error=str(exc))
            results["weather"] = {"error": str(exc)}

        try:
            results["exchange_rate"] = await _fetch_fx(validated.currency_code, client)
        except Exception as exc:
            logger.error("fx_failed", currency=validated.currency_code, error=str(exc))
            results["exchange_rate"] = {"error": str(exc)}

        results["flights"] = await _fetch_flights(
            validated.origin_iata, validated.destination_iata, validated.travel_month, client
        )

    logger.info("live_conditions_fetched", destination=validated.destination)
    return json.dumps(results, ensure_ascii=False)


def make_live_conditions_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=fetch_live_conditions,
        name="fetch_live_conditions",
        description=(
            "Fetch real-time weather, live exchange rates (USD → destination currency), "
            "and flight price estimates for a destination."
        ),
        args_schema=LiveConditionsInput,
    )
