"""Session memory management for multi-turn conversations."""

import logging

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage

from app.storage.conversation import (
    ReplaceableChatHistory,
    clear_conversation_history,
    get_conversation_history,
    get_local_session_ids,
)

logger = logging.getLogger(__name__)

# Token limits for context management
MAX_HISTORY_TOKENS = 8000  # Leave room for system prompt + current turn + tools
SUMMARIZATION_THRESHOLD = 6000  # Summarize when history exceeds this


def _count_tokens(text: str) -> int:
    """
    Approximate token count (1 token ≈ 4 chars).

    Note: This is a rough estimate. For production, use tiktoken or
    Claude's tokenizer for accurate counts.
    """
    return len(text) // 4


def _summarize_old_messages(messages: list[BaseMessage]) -> str:
    """
    Summarize old messages to reduce token count.

    For production, use an LLM to generate summary. For demo, use simple truncation.
    """
    # Simple approach: Keep first user message for context
    if messages and isinstance(messages[0], HumanMessage):
        first_msg = messages[0].content[:200]
        return f"[Previous conversation summary: User initially asked about '{first_msg}...']"
    return "[Previous conversation summary: Earlier discussion truncated]"


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    Get chat message history for a session with token management.

    Uses DynamoDB as the primary backend when configured, with an in-memory
    fallback for local development and tests. Automatically truncates and
    summarizes old history when token thresholds are exceeded.

    Args:
        session_id: Unique session identifier

    Returns:
        Chat history backend instance for the session
    """
    history = get_conversation_history(session_id)
    messages = history.messages

    # Count tokens in current history
    total_tokens = sum(_count_tokens(msg.content) for msg in messages)

    # If over threshold, keep last 10 messages and summarize rest
    if total_tokens > SUMMARIZATION_THRESHOLD and len(messages) > 10:
        logger.info(
            "summarizing_history",
            extra={
                "session_id": session_id,
                "tokens_before": total_tokens,
                "message_count": len(messages),
            },
        )

        # Keep last 10 messages (recent context)
        recent_messages = messages[-10:]
        old_messages = messages[:-10]

        # Create summary of old messages
        summary_text = _summarize_old_messages(old_messages)

        # Create new history with summary + recent messages
        # IMPORTANT: Use HumanMessage to avoid Bedrock "conversation must start with user message" error
        new_messages: list[BaseMessage] = [HumanMessage(content=summary_text), *recent_messages]

        if isinstance(history, ReplaceableChatHistory):
            history.replace_messages(new_messages)
        else:
            history.clear()
            history.add_messages(new_messages)

        tokens_after = sum(_count_tokens(msg.content) for msg in history.messages)
        logger.info(
            "summarization_complete",
            extra={
                "session_id": session_id,
                "tokens_after": tokens_after,
                "reduction": total_tokens - tokens_after,
            },
        )

        return history

    return history


def clear_session(session_id: str) -> bool:
    """
    Clear history for a specific session.

    Args:
        session_id: Session to clear

    Returns:
        True if session existed and was cleared, False otherwise
    """
    return clear_conversation_history(session_id)


def get_active_sessions() -> list[str]:
    """Get list of active in-memory session IDs for local/dev mode."""
    return get_local_session_ids()
