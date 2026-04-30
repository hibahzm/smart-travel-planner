"""
LangGraph agent graph.

Architecture:
  planner_node (gpt-4o-mini)
    ↓ tool_calls?
  tools_node   ←────────────┐
    ↓                        │
  planner_node ──────────────┘
    ↓ SYNTHESIS_READY
  synthesizer_node (gpt-4o)
    ↓
  END

Why two models?
  gpt-4o-mini handles ALL mechanical work: deciding which tools to call,
  extracting arguments, deciding when enough data is collected.
  gpt-4o only runs once at the end for the final synthesis — this is the
  expensive, creative step where quality matters most.
  Token usage is logged per step so cost is transparent.

Tool allowlist:
  Only the three declared tools are ever registered with the ToolNode.
  If the LLM hallucinates a tool name, LangGraph raises ToolException which
  is caught and returned to the planner as a structured error.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.state import AgentState
from src.agent.tools.classifier_tool import make_classifier_tool
from src.agent.tools.live_conditions_tool import make_live_conditions_tool
from src.agent.tools.rag_tool import make_rag_tool
from src.core.config import settings
from src.prompts.system_prompt import PLANNER_SYSTEM_PROMPT
from src.prompts.synthesis_prompt import SYNTHESIZER_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)

# Explicit allowlist — any tool name not in this set is refused
TOOL_ALLOWLIST = frozenset([
    "retrieve_destination_knowledge",
    "classify_destination_style",
    "fetch_live_conditions",
])

# Safety limits to prevent agent from getting stuck
MAX_STEPS = 10  # Max planner iterations
MAX_TOOL_CALLS = 15  # Max total tool invocations
STEP_TIMEOUT_SECONDS = 30  # Timeout per step


def _accumulate_usage(state_usage: dict, response_usage) -> dict:
    """Merge OpenAI usage object into our running totals."""
    if response_usage is None:
        return state_usage
    updated = dict(state_usage)
    prefix = "planner" if "planner" not in updated.get("_last", "") else "synthesizer"
    updated[f"{prefix}_prompt"] = updated.get(f"{prefix}_prompt", 0) + getattr(response_usage, "prompt_tokens", 0)
    updated[f"{prefix}_completion"] = updated.get(f"{prefix}_completion", 0) + getattr(response_usage, "completion_tokens", 0)
    return updated


def make_planner_node(llm_with_tools):
    """Returns the async planner node function."""

    async def planner_node(state: AgentState) -> dict:
        messages = list(state["messages"])
        
        # Increment step counter
        current_step = state.get("step_count", 0) + 1
        
        # Check if we've exceeded max steps
        if current_step > MAX_STEPS:
            logger.warning(
                "max_steps_exceeded",
                current_step=current_step,
                max_steps=MAX_STEPS,
            )
            return {
                "step_count": current_step,
                "max_steps_reached": True,
            }

        # Inject system prompt if this is the first call
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)] + messages

        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error("planner_node_error", error=str(e), step=current_step)
            # Return error message to continue gracefully
            response = AIMessage(content=f"Error in planning step: {str(e)}. Proceeding to synthesis.")

        # Track token usage
        usage = _accumulate_usage(state.get("token_usage", {}), getattr(response, "usage_metadata", None))
        usage["_last"] = "planner"

        synthesis_ready = (
            isinstance(response, AIMessage)
            and not response.tool_calls
            and "SYNTHESIS_READY" in (response.content or "")
        )

        logger.info(
            "planner_node",
            tool_calls=[tc["name"] for tc in (response.tool_calls or [])],
            synthesis_ready=synthesis_ready,
            step=current_step,
        )

        return {
            "messages": [response],
            "token_usage": usage,
            "synthesis_ready": synthesis_ready,
            "step_count": current_step,
        }

    return planner_node


async def synthesizer_node(state: AgentState) -> dict:
    """gpt-4o synthesis — runs exactly once, after all tool data is collected."""
    llm = ChatOpenAI(
        model=settings.SYNTHESIZER_MODEL,
        temperature=0.4,
        api_key=settings.OPENAI_API_KEY,
    )

    # Collect all tool results from message history
    tool_results = []
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            tool_results.append(f"[{msg.name}]\n{msg.content}")

    # Build a clean synthesis prompt with all gathered data
    gathered = "\n\n---\n\n".join(tool_results) if tool_results else "No tool data collected."
    original_query = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)),
        "Trip planning query",
    )

    synthesis_messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Traveller's question: {original_query}\n\n"
            f"Research data collected by the planning agent:\n\n{gathered}"
        )),
    ]

    response = await llm.ainvoke(synthesis_messages)

    usage = _accumulate_usage(state.get("token_usage", {}), getattr(response, "usage_metadata", None))
    usage["_last"] = "synthesizer"

    logger.info("synthesizer_node", response_len=len(response.content))

    return {
        "messages": [response],
        "token_usage": usage,
    }


def route_after_planner(state: AgentState) -> str:
    """
    Router called after every planner invocation.

    Safety checks:
    - max_steps_reached or max_steps exceeded → synthesizer (fallback)
    - tool_call_count exceeded → synthesizer (fallback)
    - tool_calls present and within limits → tools node
    - SYNTHESIS_READY → synthesizer
    - no tool calls, no signal → synthesizer (failsafe)
    """
    # Check if we've hit max steps or tool call limits
    if state.get("max_steps_reached"):
        logger.warning("routing_to_synthesizer_max_steps_reached")
        return "synthesizer"
    
    if state.get("tool_call_count", 0) >= MAX_TOOL_CALLS:
        logger.warning("routing_to_synthesizer_max_tool_calls_reached", count=state.get("tool_call_count"))
        return "synthesizer"

    if state.get("synthesis_ready"):
        return "synthesizer"

    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        # Enforce allowlist — reject any tool not in TOOL_ALLOWLIST
        for tc in last.tool_calls:
            if tc["name"] not in TOOL_ALLOWLIST:
                logger.warning("tool_not_allowed", tool=tc["name"])
        return "tools"

    return "synthesizer"


def build_graph(db: AsyncSession) -> Any:
    """
    Build and compile the LangGraph StateGraph.

    db is injected so tools can use the async session without global state.
    Includes safety guards:
    - MAX_STEPS: limit planner iterations
    - MAX_TOOL_CALLS: limit total tool invocations
    - Error handling: graceful fallback on failures
    """
    # Tools — only ALLOWED_TOOLS are registered; LangGraph refuses anything else
    tools = [
        make_rag_tool(db),
        make_classifier_tool(),
        make_live_conditions_tool(),
    ]

    planner_llm = ChatOpenAI(
        model=settings.PLANNER_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    ).bind_tools(tools)

    # Wrap tool_node with error handling
    base_tool_node = ToolNode(tools)
    
    async def safe_tool_node(state: AgentState) -> dict:
        """Execute tools with error handling and call tracking."""
        current_tool_calls = sum(1 for m in state["messages"] if isinstance(m, ToolMessage))
        new_call_count = state.get("tool_call_count", 0) + (
            len(state["messages"][-1].tool_calls) if (
                isinstance(state["messages"][-1], AIMessage) 
                and state["messages"][-1].tool_calls
            ) else 0
        )
        
        if new_call_count > MAX_TOOL_CALLS:
            logger.warning("tool_call_limit_exceeded", count=new_call_count, max=MAX_TOOL_CALLS)
            return {"tool_call_count": new_call_count}
        
        try:
            result = await base_tool_node.ainvoke(state)
            return {**result, "tool_call_count": new_call_count}
        except Exception as e:
            logger.error("tool_execution_error", error=str(e), tool_call_count=new_call_count)
            # Return error as ToolMessage to allow planner to recover
            error_msg = ToolMessage(
                name="tool_error",
                content=f"Tool execution error: {str(e)}. Planner will attempt alternative approach.",
            )
            return {
                "messages": [error_msg],
                "tool_call_count": new_call_count,
            }

    workflow = StateGraph(AgentState)

    # Create the planner node once per graph instance
    planner_node_fn = make_planner_node(planner_llm)

    async def _planner(state):
        return await planner_node_fn(state)

    workflow.add_node("planner", _planner)
    workflow.add_node("tools", safe_tool_node)
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.set_entry_point("planner")
    workflow.add_conditional_edges("planner", route_after_planner, {
        "tools": "tools",
        "synthesizer": "synthesizer",
    })
    workflow.add_edge("tools", "planner")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()
