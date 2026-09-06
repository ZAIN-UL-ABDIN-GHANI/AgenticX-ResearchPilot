"""
Configuration management using Pydantic Settings.

Environment variables are automatically loaded from .env file.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "ResearchPilot AI"
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "sqlite+aiosqlite:///:memory:"
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Gemini API
    gemini_api_key: str = "test-key"
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout: int = 30
    gemini_max_retries: int = 2

    # Search API
    search_api_key: str = "test-key"
    search_engine_id: str = "test-engine"
    search_timeout: int = 10
    search_max_results: int = 5

    # Agent Configuration
    max_steps: int = 8
    research_timeout: int = 300  # 5 minutes

    # Web Scraping
    fetch_timeout: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Logging
    log_format: str = "json"
    log_file: Optional[str] = None

    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
def _get_env_file():
    """Get the appropriate env file path."""
    if os.path.exists(".env.test"):
        return ".env.test"
    return ".env"


settings = Settings(_env_file=_get_env_file())
