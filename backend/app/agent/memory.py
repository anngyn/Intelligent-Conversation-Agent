"""Session memory management for multi-turn conversations."""

from langchain_community.chat_message_histories import ChatMessageHistory

# In-memory session store: session_id -> ChatMessageHistory
_session_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    """
    Get or create chat message history for a session.

    This is used by RunnableWithMessageHistory to manage conversation context.

    Args:
        session_id: Unique session identifier

    Returns:
        ChatMessageHistory instance for the session
    """
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]


def clear_session(session_id: str) -> bool:
    """
    Clear history for a specific session.

    Args:
        session_id: Session to clear

    Returns:
        True if session existed and was cleared, False otherwise
    """
    if session_id in _session_store:
        del _session_store[session_id]
        return True
    return False


def get_active_sessions() -> list[str]:
    """Get list of active session IDs."""
    return list(_session_store.keys())
