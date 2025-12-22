"""Configuration management using Pydantic Settings."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    anthropic_api_key: str
    database_path: str = "./nttp.db"
    log_level: str = "INFO"
    claude_model: str = "claude-sonnet-4-5-20250929"
    max_query_length: int = 500
    default_limit: int = 100
    max_limit: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env" if os.path.exists(".env") else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Global settings instance
settings = Settings()
