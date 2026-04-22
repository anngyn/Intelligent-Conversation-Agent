from langchain_core.messages import AIMessage, HumanMessage

from app.config import settings
from app.storage.conversation import (
    clear_conversation_history,
    get_conversation_history,
)


def test_conversation_history_falls_back_to_in_memory_when_table_missing(monkeypatch):
    """DynamoDB mode should degrade safely to local memory if no table is configured."""
    session_id = "test-session-fallback"
    clear_conversation_history(session_id)

    monkeypatch.setattr(settings, "conversation_storage_backend", "dynamodb")
    monkeypatch.setattr(settings, "conversation_table_name", "")

    history = get_conversation_history(session_id)
    history.add_messages(
        [
            HumanMessage(content=[{"text": "Hello"}, {"text": " world"}]),
            AIMessage(content=[{"text": "Hi there"}]),
        ]
    )

    assert [message.content for message in history.messages] == [
        "Hello world",
        "Hi there",
    ]

    assert clear_conversation_history(session_id) is True
    assert get_conversation_history(session_id).messages == []
