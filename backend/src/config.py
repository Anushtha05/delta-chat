"""Application configuration loaded from environment variables via pydantic-settings."""

import os
import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration is pulled from environment variables. No hardcoded secrets."""

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"

    # MySQL
    MYSQL_HOST: str = "mysql"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "delta_chat"
    MYSQL_USER: str = "delta_chat"
    MYSQL_PASSWORD: str = ""

    # MongoDB
    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DATABASE: str = "delta_chat"

    # Server
    BACKEND_PORT: int = 8000

    # Testing flag — when True, skip OPENROUTER_API_KEY validation
    TESTING: bool = False

    # ODA File Converter path for DWG→DXF conversion
    ODA_CONVERTER_PATH: str = ""

    # LLM cost estimation ($/1K tokens, approximate, for observability)
    LLM_COST_INPUT_PER_1K: float = 0.00015  # gpt-4o-mini input
    LLM_COST_OUTPUT_PER_1K: float = 0.0006  # gpt-4o-mini output

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Create and validate settings. Fail fast if OPENROUTER_API_KEY is missing (unless TESTING)."""
    settings = Settings()
    if not settings.TESTING and not settings.OPENROUTER_API_KEY:
        print(
            "ERROR: OPENROUTER_API_KEY is not set. "
            "Set it in .env or as an environment variable. "
            "To run tests without it, set TESTING=true.",
            file=sys.stderr,
        )
        sys.exit(1)
    return settings
