"""
Agent endpoint — runs the LangGraph travel planner and streams events to the frontend.

Streaming via SSE (Server-Sent Events):
  Each LangGraph event (tool_start, tool_end, token, done, error) is emitted
  as a JSON line so the React frontend can show real-time progress.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.agent.graph import build_graph
from src.api.dependencies import get_current_user
from src.core.config import settings
from src.db.session import get_db
from src.models.agent_run import AgentRun
from src.models.tool_call_log import ToolCallLog
from src.models.user import User
from src.schemas.agent import TripQueryRequest
from src.services.webhook import deliver_trip_plan

router = APIRouter(prefix="/api/agent", tags=["agent"])

logger = structlog.get_logger(__name__)


@router.post("/query")
async def query_agent(
    body: TripQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream the agent's response as SSE events.

    Event types:
      { "event": "tool_start",  "data": { "tool": "...", "input": {...} } }
      { "event": "tool_end",    "data": { "tool": "...", "output": "...", "duration_ms": N } }
      { "event": "token",       "data": { "content": "..." } }
      { "event": "done",        "data": { "run_id": "...", "token_usage": {...} } }
      { "event": "error",       "data": { "message": "..." } }
    """
    run_id = uuid.uuid4()

    # Create run record in DB
    run = AgentRun(
        id=run_id,
        user_id=current_user.id,
        query=body.query,
        status="running",
    )
    db.add(run)
    await db.commit()

    async def event_generator():
        try:
            graph = build_graph(db)
            initial_state = {
                "messages": [HumanMessage(content=body.query)],
                "user_id": str(current_user.id),
                "run_id": str(run_id),
                "token_usage": {},
                "tool_call_logs": [],
                "synthesis_ready": False,
            }

            tool_start_times: dict[str, float] = {}
            final_response = ""
            final_token_usage = {}

            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event["event"]
                name = event.get("name", "")

                # ── Tool start ────────────────────────────────────────────────
                if kind == "on_tool_start" and name in ("retrieve_destination_knowledge", "classify_destination_style", "fetch_live_conditions"):
                    tool_input = event.get("data", {}).get("input", {})
                    tool_start_times[name] = __import__("time").perf_counter()
                    yield {
                        "event": "tool_start",
                        "data": json.dumps({"tool": name, "input": tool_input}),
                    }

                # ── Tool end ──────────────────────────────────────────────────
                elif kind == "on_tool_end" and name in ("retrieve_destination_knowledge", "classify_destination_style", "fetch_live_conditions"):
                    output = event.get("data", {}).get("output", "")
                    duration_ms = int(
                        (__import__("time").perf_counter() - tool_start_times.get(name, 0)) * 1000
                    )

                    # Persist tool call log
                    try:
                        input_data = event.get("data", {}).get("input", {})
                        log = ToolCallLog(
                            run_id=run_id,
                            tool_name=name,
                            tool_input=input_data if isinstance(input_data, dict) else {"raw": str(input_data)},
                            tool_output={"result": str(output)[:5000]} if output else None,
                            duration_ms=duration_ms,
                        )
                        db.add(log)
                        await db.commit()
                    except Exception as log_exc:
                        logger.warning("tool_log_failed", error=str(log_exc))

                    yield {
                        "event": "tool_end",
                        "data": json.dumps({"tool": name, "output": str(output)[:2000], "duration_ms": duration_ms}),
                    }

                # ── LLM streaming tokens (synthesizer only) ───────────────────
                elif kind == "on_chat_model_stream" and event.get("metadata", {}).get("langgraph_node") == "synthesizer":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        final_response += chunk.content
                        yield {
                            "event": "token",
                            "data": json.dumps({"content": chunk.content}),
                        }

                # ── Run end — capture final state ─────────────────────────────
                elif kind == "on_chain_end" and name == "LangGraph":
                    output = event.get("data", {}).get("output", {})
                    final_token_usage = output.get("token_usage", {})
                    # Get final response from messages if streaming missed it
                    if not final_response:
                        msgs = output.get("messages", [])
                        for msg in reversed(msgs):
                            if isinstance(msg, AIMessage) and msg.content and "SYNTHESIS_READY" not in msg.content:
                                final_response = msg.content
                                break

            # ── Persist completed run ─────────────────────────────────────────
            run.status = "completed"
            run.response = final_response
            run.token_usage = {k: v for k, v in final_token_usage.items() if not k.startswith("_")}
            run.completed_at = datetime.now(UTC)
            db.add(run)
            await db.commit()

            # ── Fire webhook (fire-and-forget, failure isolated) ───────────────
            if current_user.webhook_url or settings.DISCORD_WEBHOOK_URL:
                import asyncio
                asyncio.create_task(
                    deliver_trip_plan(
                        str(run_id),
                        body.query,
                        final_response,
                        current_user.username,
                        current_user.webhook_url,
                    )
                )

            yield {
                "event": "done",
                "data": json.dumps({
                    "run_id": str(run_id),
                    "token_usage": run.token_usage,
                }),
            }

        except Exception as exc:
            logger.error("agent_error", run_id=str(run_id), error=str(exc))
            run.status = "failed"
            db.add(run)
            await db.commit()
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}),
            }

    return EventSourceResponse(event_generator())
