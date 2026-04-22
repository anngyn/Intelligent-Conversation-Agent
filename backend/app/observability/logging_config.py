"""Structured logging setup for CloudWatch-friendly JSON logs."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.config import settings

_STANDARD_RECORD_FIELDS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class StructuredJSONFormatter(logging.Formatter):
    """Render logs as JSON and scrub basic PII patterns before emission."""

    PII_PATTERNS = [
        (r"\b\d{4}\b", "[SSN_REDACTED]"),
        (r"\b\d{4}-\d{2}-\d{2}\b", "[DOB_REDACTED]"),
        (r"\b\d{2}/\d{2}/\d{4}\b", "[DOB_REDACTED]"),
        (r'"full_name":\s*"[^"]*"', '"full_name": "[REDACTED]"'),
        (r'"last4_ssn":\s*"[^"]*"', '"last4_ssn": "[REDACTED]"'),
        (r'"date_of_birth":\s*"[^"]*"', '"date_of_birth": "[REDACTED]"'),
    ]

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "agent-backend",
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            log_entry[key] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        serialized = json.dumps(log_entry, default=str, ensure_ascii=True)
        for pattern, replacement in self.PII_PATTERNS:
            serialized = re.sub(pattern, replacement, serialized)
        return serialized


def setup_structured_logging() -> None:
    """Configure root logging once with JSON output."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level.upper())
