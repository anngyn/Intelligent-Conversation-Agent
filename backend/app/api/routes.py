"""API route definitions."""

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.agent.memory import clear_session, get_session_history
from app.api.schemas import ChatEvent, ChatRequest, EventType, HealthResponse
from app.config import settings
from app.observability import emit_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


_agent: RunnableWithMessageHistory | None = None


def set_agent(agent: RunnableWithMessageHistory) -> None:
    """Set the global agent instance (called from main.py on startup)."""
    global _agent
    _agent = agent


async def generate_stream(session_id: str, message: str) -> AsyncIterator[str]:
    """
    Generate SSE events from agent execution.

    Args:
        session_id: Session identifier for memory
        message: User message

    Yields:
        SSE-formatted event strings
    """
    if _agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    stream_start = time.perf_counter()
    token_count = 0
    tool_names: set[str] = set()

    try:
        last_event_time = time.time()

        async for event in _agent.astream_events(
            {"input": message},
            config={"configurable": {"session_id": session_id}},
            version="v2",
        ):
            event_type = event.get("event")

            # Keepalive every 15 seconds (prevent ALB/proxy timeout)
            if time.time() - last_event_time > 15:
                yield ": keepalive\n\n"
                last_event_time = time.time()

            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    # Handle both string and content_blocks format
                    if isinstance(chunk.content, str):
                        content_str = chunk.content
                    elif isinstance(chunk.content, list):
                        # Extract text from content blocks
                        content_str = "".join(
                            block.get("text", "") if isinstance(block, dict) else str(block)
                            for block in chunk.content
                        )
                    else:
                        content_str = str(chunk.content)

                    if content_str:
                        token_count += 1
                        chat_event = ChatEvent(type=EventType.TOKEN, data=content_str)
                        yield f"data: {chat_event.model_dump_json()}\n\n"
                        last_event_time = time.time()

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_names.add(tool_name)
                chat_event = ChatEvent(
                    type=EventType.TOOL_START,
                    data={"tool": tool_name},
                )
                yield f"data: {chat_event.model_dump_json()}\n\n"

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "unknown")
                chat_event = ChatEvent(
                    type=EventType.TOOL_END,
                    data={"tool": tool_name},
                )
                yield f"data: {chat_event.model_dump_json()}\n\n"

        total_latency_ms = round((time.perf_counter() - stream_start) * 1000, 2)
        logger.info(
            "chat_stream_completed",
            extra={
                "session_id": session_id,
                "latency_ms": total_latency_ms,
                "token_events": token_count,
                "tool_count": len(tool_names),
            },
        )
        emit_metrics(
            metrics=[
                {"Name": "AgentLatency", "Unit": "Milliseconds", "Value": total_latency_ms},
                {"Name": "ToolCallsPerRequest", "Unit": "Count", "Value": len(tool_names)},
                {"Name": "StreamTokenEvents", "Unit": "Count", "Value": token_count},
            ],
            dimensions={"Endpoint": "chat"},
            properties={"session_id": session_id},
        )

        final_event = ChatEvent(type=EventType.DONE)
        yield f"data: {final_event.model_dump_json()}\n\n"

    except asyncio.CancelledError:
        # Client disconnected
        logger.info("sse_client_disconnect", extra={"session_id": session_id})
        raise

    except Exception as e:
        import traceback

        full_trace = traceback.format_exc()
        total_latency_ms = round((time.perf_counter() - stream_start) * 1000, 2)
        logger.error(
            "sse_stream_failed",
            extra={
                "session_id": session_id,
                "error": str(e),
                "trace": full_trace,
                "latency_ms": total_latency_ms,
            },
        )
        emit_metrics(
            metrics=[
                {"Name": "AgentLatency", "Unit": "Milliseconds", "Value": total_latency_ms},
                {"Name": "ErrorRate", "Unit": "Count", "Value": 1},
            ],
            dimensions={"Endpoint": "chat", "ErrorType": "sse_stream_failed"},
            properties={"session_id": session_id},
        )
        error_event = ChatEvent(type=EventType.ERROR, data="An error occurred. Please try again.")
        yield f"data: {error_event.model_dump_json()}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Chat endpoint with streaming responses.

    Accepts a message and session ID, returns Server-Sent Events (SSE) stream
    with tokens, tool calls, and completion status.
    """
    # Monitor conversation length
    history = get_session_history(request.session_id)
    turn_count = len(history.messages) // 2  # Each turn = 1 user + 1 assistant message

    if turn_count > 50:
        logger.warning(
            "very_long_conversation",
            extra={"session_id": request.session_id, "turn_count": turn_count},
        )
    emit_metrics(
        metrics=[
            {"Name": "ConversationTurns", "Unit": "Count", "Value": turn_count},
            {"Name": "ChatRequests", "Unit": "Count", "Value": 1},
        ],
        dimensions={"Endpoint": "chat"},
        properties={"session_id": request.session_id},
    )

    return StreamingResponse(
        generate_stream(request.session_id, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Clear conversation history for a session."""
    success = clear_session(session_id)
    return {"success": success, "session_id": session_id}


@router.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
    )
