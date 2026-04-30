"""
Webhook delivery service — fires trip plan to Discord/Slack after agent completes.

Design decisions:
  - tenacity retry with exponential backoff (3 attempts, 1–10 s)
  - hard timeout per attempt (WEBHOOK_TIMEOUT_SECONDS from config)
  - webhook failure is caught, logged, and NEVER bubbles up to the user response
  - structured log on every attempt and failure for observability
"""

from __future__ import annotations

import json
import logging as _logging

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from src.core.config import settings

logger = structlog.get_logger(__name__)
_retry_logger = _logging.getLogger(__name__)


def _discord_payload(run_id: str, query: str, response: str, username: str) -> dict:
    truncated = response[:1800] + "…" if len(response) > 1800 else response
    return {
        "username": "Smart Travel Planner 🗺️",
        "embeds": [
            {
                "title": f"Trip Plan for {username}",
                "description": truncated,
                "color": 0x1DB954,
                "fields": [
                    {"name": "Query", "value": query[:256], "inline": False},
                    {"name": "Run ID", "value": str(run_id), "inline": True},
                ],
                "footer": {"text": "Smart Travel Planner · AI-powered"},
            }
        ],
    }


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(settings.WEBHOOK_MAX_RETRIES),
    before_sleep=before_sleep_log(_retry_logger, _logging.WARNING),
    reraise=False,
)
async def _post_webhook(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


async def deliver_trip_plan(
    run_id: str,
    query: str,
    response: str,
    username: str,
    webhook_url: str | None = None,
) -> bool:
    """
    Fire the trip plan to the configured webhook.

    Returns True on success, False on failure.
    Failure is always isolated — never raises to the caller.
    """
    valid_user_url = webhook_url if (webhook_url and webhook_url.startswith(("http://", "https://"))) else None
    url = valid_user_url or settings.DISCORD_WEBHOOK_URL
    if not url:
        logger.info("webhook_skipped", reason="no url configured")
        return False

    payload = _discord_payload(run_id, query, response, username)

    try:
        await _post_webhook(url, payload)
        logger.info("webhook_delivered", run_id=run_id, url=url[:50])
        return True
    except Exception as exc:
        logger.error(
            "webhook_failed",
            run_id=run_id,
            error=str(exc),
            url=url[:50],
        )
        return False
