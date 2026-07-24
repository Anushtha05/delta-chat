"""Request tracing — structured per-request traces with stage timings and metadata.

Each request gets a RequestTrace keyed by request_id (uuid4). Stages track
start/end time, duration_ms, and arbitrary metadata. On completion, the trace
is serialized to JSON and persisted to both file and MongoDB.
"""

import json
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Context variable holding the current request trace
_current_trace: ContextVar["RequestTrace | None"] = ContextVar("_current_trace", default=None)

_TRACES_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "traces"


def get_current_trace() -> "RequestTrace | None":
    """Get the active trace from context, or None."""
    return _current_trace.get()


def get_request_id() -> str | None:
    """Get the current request_id from the active trace, or None."""
    trace = _current_trace.get()
    return trace.request_id if trace else None


class Stage:
    """A named stage within a request trace."""

    def __init__(self, name: str):
        self.name = name
        self.start_time: float = 0
        self.end_time: float = 0
        self.duration_ms: float = 0
        self.metadata: dict[str, Any] = {}
        self.error: str | None = None

    def __enter__(self) -> "Stage":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if exc_type:
            self.error = f"{exc_type.__name__}: {exc_val}"
        return False  # Don't suppress exceptions

    def set(self, key: str, value: Any) -> None:
        """Set a metadata field on this stage."""
        self.metadata[key] = value

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }
        if self.error:
            d["error"] = self.error
        return d


class RequestTrace:
    """Full trace for a single request, containing multiple stages."""

    def __init__(self, request_id: str | None = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.start_time = time.time()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stages: list[Stage] = []
        self.endpoint: str = ""
        self.status: str = "in_progress"
        self._token = _current_trace.set(self)

    def stage(self, name: str) -> Stage:
        """Create a new stage context manager."""
        s = Stage(name)
        self.stages.append(s)
        return s

    def finish(self, status: str = "success") -> dict:
        """Finalize the trace and persist it. Returns the trace dict."""
        self.status = status
        total_ms = round((time.time() - self.start_time) * 1000, 2)

        trace_dict = {
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "started_at": self.started_at,
            "total_duration_ms": total_ms,
            "status": self.status,
            "stages": [s.to_dict() for s in self.stages],
        }

        # Persist
        self._write_file(trace_dict)
        self._write_mongo(trace_dict)

        # Reset context
        _current_trace.set(None)

        return trace_dict

    def _write_file(self, trace_dict: dict) -> None:
        """Write trace JSON to outputs/traces/{request_id}.json."""
        try:
            _TRACES_DIR.mkdir(parents=True, exist_ok=True)
            path = _TRACES_DIR / f"{self.request_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(trace_dict, f, indent=2, default=str)
        except Exception:
            pass  # Tracing failure must never crash the request

    def _write_mongo(self, trace_dict: dict) -> None:
        """Insert trace into MongoDB collection `traces`."""
        try:
            from src.db.mongo import get_db
            db = get_db()
            db["traces"].replace_one(
                {"request_id": self.request_id},
                trace_dict,
                upsert=True,
            )
        except Exception:
            pass  # Tracing failure must never crash the request
