"""Configuration management using Pydantic Settings."""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database (SQL: SQLite file by default)
    DATABASE_URL: str = "sqlite:///./opspilot.db"

    # Execution Modes & Safety
    MODE: str = "simulation"  # simulation, sandbox, live
    ALLOW_LIVE: bool = False
    MAX_EXTERNAL_ACTIONS: int = 20
    SANDBOX_REDIRECT_TO: Optional[str] = None

    # CORS & Security
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )
    DEV_AUTH_BYPASS: bool = True
    JWT_SECRET: str = ""
    ENV: str = "dev"  # dev, prod, test

    # LLM & Planner (OpenRouter / Gemini)
    LLM_MODEL: str = "openrouter/google/gemini-2.0-flash-exp:free"
    LLM_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    USE_CACHED_PLANS: bool = False

    # Email & Outbound Messaging (Web3Forms / SMTP)
    WEB3FORMS_ACCESS_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "ops@example.com"

    # Owner notifications: best-effort email on plan create/approve. No-op without OWNER_EMAIL.
    OWNER_NOTIFY: bool = True
    OWNER_EMAIL: str = ""

    # Telegram Messaging
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_TEST_CHAT_ID: str = ""

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_SHEET_TEST_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a clean list."""
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

