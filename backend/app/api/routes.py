"""API route definitions."""

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.agent.memory import clear_session
from app.api.schemas import ChatEvent, ChatRequest, EventType, HealthResponse
from app.config import settings

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

    try:
        async for event in _agent.astream_events(
            {"input": message},
            config={"configurable": {"session_id": session_id}},
            version="v2",
        ):
            event_type = event.get("event")

            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    chat_event = ChatEvent(type=EventType.TOKEN, data=chunk.content)
                    yield f"data: {chat_event.model_dump_json()}\n\n"

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "unknown")
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

        final_event = ChatEvent(type=EventType.DONE)
        yield f"data: {final_event.model_dump_json()}\n\n"

    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        error_event = ChatEvent(type=EventType.ERROR, data=str(e))
        yield f"data: {error_event.model_dump_json()}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Chat endpoint with streaming responses.

    Accepts a message and session ID, returns Server-Sent Events (SSE) stream
    with tokens, tool calls, and completion status.
    """
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
