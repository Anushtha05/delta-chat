"""LLM call telemetry — records full prompt/response to MongoDB for debugging.

Every LLMClient.generate() call stores the full exchange in `llm_calls` collection,
keyed by request_id. A truncated preview (~500 chars) is also returned for inclusion
in the trace stage metadata.
"""

import logging
from datetime import datetime, timezone

from src.observability.tracing import get_request_id

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 500


def record_llm_call(
    system_prompt: str,
    user_prompt: str,
    response_text: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
    duration_ms: float,
) -> dict:
    """Record a full LLM call to MongoDB and return a preview for trace metadata.

    Returns a dict suitable for inclusion in trace stage metadata (truncated).
    """
    request_id = get_request_id() or "unknown"

    full_record = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response_text": response_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": estimated_cost,
        "duration_ms": duration_ms,
    }

    # Persist to MongoDB
    try:
        from src.db.mongo import get_db
        db = get_db()
        db["llm_calls"].insert_one(full_record.copy())
    except Exception as e:
        logger.warning("Failed to persist LLM call to MongoDB: %s", e)

    # Return truncated preview for trace metadata
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": round(estimated_cost, 6),
        "duration_ms": duration_ms,
        "system_prompt_preview": system_prompt[:_PREVIEW_CHARS],
        "user_prompt_preview": user_prompt[:_PREVIEW_CHARS],
        "response_preview": response_text[:_PREVIEW_CHARS],
    }


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts using configured rates."""
    try:
        from src.config import get_settings
        settings = get_settings()
        cost = (input_tokens / 1000.0) * settings.LLM_COST_INPUT_PER_1K
        cost += (output_tokens / 1000.0) * settings.LLM_COST_OUTPUT_PER_1K
        return round(cost, 6)
    except Exception:
        return 0.0
