"""Application settings. Every env var is listed in docs/CONTRACTS.md section 13 and in .env.example."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The repo-root .env is the normal place; backend/.env overrides it if present.
        env_file=(_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Infrastructure
    DATABASE_URL: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    JWT_SECRET: str = "change-me"
    ENCRYPTION_KEY: str = ""  # Fernet key; see .env.example for how to generate one

    # Public URL (webhooks, links in notifications)
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Mocks: on by default so nobody needs real keys to develop
    USE_MOCK_ADAPTERS: bool = True
    USE_MOCK_LLM: bool = True

    # LLM (provider-neutral; see docs/CONTRACTS.md section 6 and docs/setup-accounts.md)
    LLM_PROVIDER: str = "openai_compatible"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL_SMART: str = ""
    LLM_MODEL_FAST: str = ""
    LLM_MAX_CONCURRENCY: int = 2

    # External services
    GOOGLE_PLACES_API_KEY: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_GRAPH_VERSION: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""

    # Files
    UPLOAD_DIR: str = "./data/uploads"

    # Misc
    TIMEZONE: str = "Africa/Cairo"
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
