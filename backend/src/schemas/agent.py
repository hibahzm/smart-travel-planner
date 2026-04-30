from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TripQueryRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000, description="Natural-language travel question")


class ToolCallDetail(BaseModel):
    tool_name: str
    tool_input: dict
    tool_output: dict | None
    error: str | None
    duration_ms: int | None
    called_at: datetime

    model_config = {"from_attributes": True}


class AgentRunResponse(BaseModel):
    run_id: uuid.UUID = Field(alias="id")
    query: str
    response: str | None
    status: str
    token_usage: dict
    tool_calls: list[ToolCallDetail]
    started_at: datetime
    completed_at: datetime | None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


class RunListResponse(BaseModel):
    runs: list[AgentRunResponse]
    total: int


# SSE event types streamed to the frontend
class StreamEvent(BaseModel):
    event: str  # "tool_start" | "tool_end" | "token" | "done" | "error"
    data: dict
