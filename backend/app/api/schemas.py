"""Pydantic models for API requests and responses."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    session_id: str = Field(..., description="Unique session identifier (UUID)")
    message: str = Field(..., min_length=1, description="User message")


class EventType(StrEnum):
    """Types of SSE events."""

    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    ERROR = "error"
    DONE = "done"


class ChatEvent(BaseModel):
    """SSE event model."""

    type: EventType
    data: str | dict | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
