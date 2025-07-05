# src/marbix/core/config.py

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application configuration loaded from environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False
    )

    # Database connection URL
    DATABASE_URL: str = Field(
        "postgresql://postgres:postgres@localhost:5432/postgres",
        env="DATABASE_URL"
    )

    # JWT / auth
    AUTH_SECRET: str = Field("dev-secret-key", env="AUTH_SECRET")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(30, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = Field(..., env="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_ID_EXTENSION: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID_EXTENSION")
    GOOGLE_CLIENT_SECRET: str = Field(..., env="GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = Field(..., env="GOOGLE_REDIRECT_URI")

    # Perplexity / OpenAI API keys
    PERPLEXITY_API_KEY: str = Field(..., env="PERPLEXITY_API_KEY")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")

    # Make.com webhook & API key
    WEBHOOK_URL: str = Field(..., env="WEBHOOK_URL")
    MAKE_API_KEY: str = Field(..., env="MAKE_API_KEY")
    
    # Make webhook settings
    MAKE_WEBHOOK_URL: str = Field(..., env="MAKE_WEBHOOK_URL")
    API_BASE_URL: str = Field(
        "https://your-api.onrender.com",
        env="API_BASE_URL"
    )
    
    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: int = Field(
        30,
        env="WS_HEARTBEAT_INTERVAL"
    )
    WS_CONNECTION_TIMEOUT: int = Field(
        300,
        env="WS_CONNECTION_TIMEOUT"
    )
    
    # Request cleanup
    REQUEST_CLEANUP_DELAY: int = Field(
        300,
        env="REQUEST_CLEANUP_DELAY"
    )

# single, application‐wide settings instance
settings = Settings()