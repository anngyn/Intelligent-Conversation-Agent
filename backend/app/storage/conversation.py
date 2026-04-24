"""Conversation history storage backends."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    message_to_dict,
    messages_from_dict,
)

from app.config import settings
from app.observability import emit_metrics

logger = logging.getLogger(__name__)

_in_memory_histories: dict[str, NormalizedInMemoryHistory] = {}
_warned_backends: set[str] = set()


class MessageNormalizationMixin:
    """Normalize model/tool content blocks before persisting them."""

    @staticmethod
    def _stringify_content_blocks(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                MessageNormalizationMixin._stringify_content_blocks(item) for item in content
            )
        if isinstance(content, dict):
            if "text" in content:
                return str(content["text"])
            if "content" in content:
                return MessageNormalizationMixin._stringify_content_blocks(content["content"])
            return ""
        return str(content)

    def _normalize_message(
        self,
        message: Any,
        *,
        default_role: str = "assistant",
    ) -> BaseMessage:
        if isinstance(message, BaseMessage):
            if isinstance(message.content, list):
                text_content = self._stringify_content_blocks(message.content)
                if isinstance(message, HumanMessage):
                    return HumanMessage(
                        content=text_content,
                        additional_kwargs=message.additional_kwargs,
                        response_metadata=message.response_metadata,
                        name=message.name,
                        id=message.id,
                    )
                if isinstance(message, AIMessage):
                    return AIMessage(
                        content=text_content,
                        additional_kwargs=message.additional_kwargs,
                        response_metadata=message.response_metadata,
                        tool_calls=message.tool_calls,
                        invalid_tool_calls=message.invalid_tool_calls,
                        usage_metadata=message.usage_metadata,
                        name=message.name,
                        id=message.id,
                    )
            return message

        if isinstance(message, str):
            return (
                HumanMessage(content=message)
                if default_role == "human"
                else AIMessage(content=message)
            )

        if isinstance(message, dict):
            if "role" in message and "content" in message:
                role = message["role"]
                content = self._stringify_content_blocks(message["content"])
                return (
                    HumanMessage(content=content)
                    if role in {"human", "user"}
                    else AIMessage(content=content)
                )

            if "type" in message and "text" in message:
                return AIMessage(content=self._stringify_content_blocks(message))

            if "content" in message:
                return AIMessage(content=self._stringify_content_blocks(message["content"]))

        return AIMessage(content=self._stringify_content_blocks(message))

    def _normalize_messages(self, messages: Sequence[BaseMessage]) -> list[BaseMessage]:
        normalized_messages: list[BaseMessage] = []
        for index, message in enumerate(messages):
            default_role = "human" if index == 0 else "assistant"
            normalized_messages.append(self._normalize_message(message, default_role=default_role))
        return normalized_messages


class ReplaceableChatHistory(BaseChatMessageHistory):
    """Extension point for histories that can rewrite their full message list."""

    def replace_messages(self, messages: Sequence[BaseMessage]) -> None:
        raise NotImplementedError


class NormalizedInMemoryHistory(MessageNormalizationMixin, ReplaceableChatHistory):
    """Local fallback history used in dev/test without DynamoDB."""

    def __init__(self) -> None:
        self._messages: list[BaseMessage] = []

    @property
    def messages(self) -> list[BaseMessage]:
        return list(self._messages)

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        self._messages.extend(self._normalize_messages(messages))

    def replace_messages(self, messages: Sequence[BaseMessage]) -> None:
        self._messages = self._normalize_messages(messages)

    def clear(self) -> None:
        self._messages = []


class DynamoDBConversationHistory(MessageNormalizationMixin, ReplaceableChatHistory):
    """DynamoDB-backed conversation history using one item per message."""

    def __init__(
        self,
        session_id: str,
        *,
        table_name: str,
        ttl_days: int,
        region_name: str,
        endpoint_url: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.ttl_days = ttl_days
        self.table = _get_dynamodb_table(table_name, region_name, endpoint_url or None)

    @property
    def messages(self) -> list[BaseMessage]:
        start_time = time.perf_counter()
        items = self._query_items()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        emit_metrics(
            metrics=[
                {"Name": "ConversationReadLatency", "Unit": "Milliseconds", "Value": latency_ms},
                {"Name": "ConversationMessagesRead", "Unit": "Count", "Value": len(items)},
            ],
            dimensions={"Backend": "dynamodb"},
            properties={"session_id": self.session_id},
        )
        if not items:
            return []

        serialized_messages = [item["message"] for item in items]
        return self._normalize_messages(messages_from_dict(serialized_messages))

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        start_time = time.perf_counter()
        normalized_messages = self._normalize_messages(messages)
        ttl = int(time.time()) + (self.ttl_days * 24 * 60 * 60)

        # Ensure strictly increasing timestamps for message ordering
        base_timestamp = int(time.time() * 1000)

        with self.table.batch_writer() as batch:
            for index, message in enumerate(normalized_messages):
                # Add index to guarantee ordering within same millisecond
                created_at = base_timestamp + index
                batch.put_item(
                    Item={
                        "session_id": self.session_id,
                        "message_key": f"{created_at:013d}#{uuid.uuid4().hex}",
                        "created_at": created_at,
                        "message_type": message.type,
                        "message": message_to_dict(message),
                        "ttl": ttl,
                    }
                )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        emit_metrics(
            metrics=[
                {"Name": "ConversationWriteLatency", "Unit": "Milliseconds", "Value": latency_ms},
                {
                    "Name": "ConversationMessagesWritten",
                    "Unit": "Count",
                    "Value": len(normalized_messages),
                },
            ],
            dimensions={"Backend": "dynamodb"},
            properties={"session_id": self.session_id},
        )

    def replace_messages(self, messages: Sequence[BaseMessage]) -> None:
        self.clear()
        self.add_messages(messages)

    def clear(self) -> None:
        items = self._query_items(projection_expression="session_id, message_key")
        if not items:
            return

        with self.table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={
                        "session_id": item["session_id"],
                        "message_key": item["message_key"],
                    }
                )

    def _query_items(self, projection_expression: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("session_id").eq(self.session_id),
            "ScanIndexForward": True,
            "ConsistentRead": True,
        }
        if projection_expression:
            query_kwargs["ProjectionExpression"] = projection_expression

        while True:
            response = self.table.query(**query_kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        return items


@lru_cache(maxsize=8)
def _get_dynamodb_table(table_name: str, region_name: str, endpoint_url: str | None):
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=region_name,
        endpoint_url=endpoint_url,
    )
    return dynamodb.Table(table_name)


def get_conversation_history(session_id: str) -> ReplaceableChatHistory:
    """Return the configured conversation history backend for a session."""
    backend = settings.conversation_storage_backend.lower()
    if backend == "dynamodb":
        if settings.conversation_table_name:
            return DynamoDBConversationHistory(
                session_id,
                table_name=settings.conversation_table_name,
                ttl_days=settings.conversation_ttl_days,
                region_name=settings.aws_region,
                endpoint_url=settings.dynamodb_endpoint_url,
            )

        _warn_once(
            "conversation:dynamodb",
            "DynamoDB conversation backend selected but conversation_table_name is empty; using in-memory fallback.",
        )

    history = _in_memory_histories.get(session_id)
    if history is None:
        history = NormalizedInMemoryHistory()
        _in_memory_histories[session_id] = history
    return history


def clear_conversation_history(session_id: str) -> bool:
    """Clear a conversation history from the active backend."""
    backend = settings.conversation_storage_backend.lower()
    if backend == "dynamodb" and settings.conversation_table_name:
        history = DynamoDBConversationHistory(
            session_id,
            table_name=settings.conversation_table_name,
            ttl_days=settings.conversation_ttl_days,
            region_name=settings.aws_region,
            endpoint_url=settings.dynamodb_endpoint_url,
        )
        history.clear()
        return True

    if session_id in _in_memory_histories:
        del _in_memory_histories[session_id]
        return True
    return False


def get_local_session_ids() -> list[str]:
    """Return active in-memory sessions for local/dev mode."""
    return list(_in_memory_histories.keys())


def _warn_once(key: str, message: str) -> None:
    if key in _warned_backends:
        return
    logger.warning(message)
    _warned_backends.add(key)
