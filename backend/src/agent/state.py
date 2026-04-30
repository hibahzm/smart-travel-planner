"""LangGraph state definition for the travel planner agent."""

from __future__ import annotations

from typing import Annotated, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    run_id: str
    # Accumulated token usage across all LLM calls in this run
    # Keys: planner_prompt, planner_completion, synthesizer_prompt, synthesizer_completion
    token_usage: dict[str, int]
    # Logs of each tool invocation — persisted to DB after the run
    tool_call_logs: list[dict]
    # Flag set by the planner when all tools have been called
    synthesis_ready: bool
    # Safety limits tracking
    step_count: int  # Track planner iterations
    tool_call_count: int  # Track total tool invocations
    max_steps_reached: bool  # Flag when safety limit exceeded
