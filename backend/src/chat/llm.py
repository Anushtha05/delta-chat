"""LLM client abstraction with OpenRouter implementation.

Designed to be swappable — any LLM provider can be plugged in by implementing LLMClient.
The OpenRouterClient uses the OpenAI-compatible chat completions API via httpx.
"""

import logging
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ─── Response model ───────────────────────────────────────────────────────────


class LLMResponse(BaseModel):
    """Standard response from any LLM client."""
    text: str
    input_tokens: int
    output_tokens: int
    model: str


# ─── Errors ───────────────────────────────────────────────────────────────────


class LLMRequestError(Exception):
    """Raised when the LLM API returns a non-200 response or times out."""

    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ─── Abstract interface ───────────────────────────────────────────────────────


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Generate a completion given system and user prompts."""
        ...


# ─── OpenRouter implementation ────────────────────────────────────────────────

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient(LLMClient):
    """LLM client for OpenRouter (OpenAI-compatible API).

    API key and model are loaded from config — never hardcoded, never logged.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY must be provided (non-empty).")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:
        """Call OpenRouter chat completions API."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://delta-chat.local",
            "X-Title": "Delta Chat",
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Low temperature for factual/grounded answers
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(_OPENROUTER_URL, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise LLMRequestError(
                f"OpenRouter request timed out after {self._timeout}s",
                status_code=None,
                body=str(e),
            ) from e
        except httpx.RequestError as e:
            raise LLMRequestError(
                f"OpenRouter request failed: {e}",
                status_code=None,
                body=str(e),
            ) from e

        if response.status_code != 200:
            raise LLMRequestError(
                f"OpenRouter returned HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )

        data = response.json()

        # Parse the OpenAI-compatible response
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            model_used = data.get("model", self._model)
        except (KeyError, IndexError) as e:
            raise LLMRequestError(
                f"Unexpected response structure from OpenRouter: {e}",
                status_code=200,
                body=str(data),
            ) from e

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model_used,
        )


def get_llm_client() -> OpenRouterClient:
    """Factory: create an OpenRouterClient from application config."""
    from src.config import get_settings
    settings = get_settings()
    return OpenRouterClient(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
    )
