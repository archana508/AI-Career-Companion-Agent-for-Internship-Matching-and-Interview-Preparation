"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "AI Internship Agent"
    debug: bool = False

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/internship_agent"
    )

    # File uploads
    upload_dir: Path = Path("uploads")
    max_upload_size_mb: int = 10

    # Ollama / AI
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2:1b"

    # JWT authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Authentication cookies
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"

    # Frontend URLs allowed to communicate with FastAPI
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()