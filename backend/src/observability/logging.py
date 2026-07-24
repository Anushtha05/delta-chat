"""Structured JSON logging for the entire application.

Every log line includes: timestamp, level, event, request_id (if available),
plus event-specific fields. Configured at app startup via setup_logging().
"""

import json
import logging
import sys
from datetime import datetime, timezone

from src.observability.tracing import get_request_id


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON with request context."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "logger": record.name,
            "request_id": get_request_id(),
        }

        # Add any extra fields attached to the record
        for key in ("document_id", "revision", "format", "page", "confidence",
                    "error_type", "error_detail", "file_path", "duration_ms",
                    "changes_found", "chunks_retrieved", "input_tokens",
                    "output_tokens", "model", "status_code"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        # Include message if different from event
        msg = record.getMessage()
        if msg and msg != log_entry["event"]:
            log_entry["message"] = msg

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the whole application."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, level: int, event: str, **kwargs) -> None:
    """Emit a structured log event with extra fields."""
    extra = {"event": event}
    extra.update(kwargs)
    logger.log(level, event, extra=extra)
