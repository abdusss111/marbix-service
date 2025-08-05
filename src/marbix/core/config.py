# src/marbix/core/config.py

from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from arq.connections import RedisSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment."""

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

    # Redis configuration
    REDIS_URL: str = Field(
        "redis://localhost:6379/0",
        env="REDIS_URL"
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
    ANTHROPIC_API_KEY: str = Field(..., env="ANTHROPIC_API_KEY")

    # Make.com webhook & API key (legacy)
    WEBHOOK_URL: Optional[str] = Field(None, env="WEBHOOK_URL")
    MAKE_API_KEY: Optional[str] = Field(None, env="MAKE_API_KEY")

    # API base URL for callbacks
    API_BASE_URL: str = Field(
        "https://your-api.onrender.com",
        env="API_BASE_URL"
    )

    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: int = Field(30, env="WS_HEARTBEAT_INTERVAL")
    WS_CONNECTION_TIMEOUT: int = Field(300, env="WS_CONNECTION_TIMEOUT")

    # Request cleanup
    REQUEST_CLEANUP_DELAY: int = Field(300, env="REQUEST_CLEANUP_DELAY")

    # ARQ Worker settings
    ARQ_JOB_TIMEOUT: int = Field(1800, env="ARQ_JOB_TIMEOUT")  # 30 minutes
    ARQ_MAX_TRIES: int = Field(3, env="ARQ_MAX_TRIES")
    ARQ_RETRY_DELAY: int = Field(60, env="ARQ_RETRY_DELAY")  # 1 minute

    @validator('REDIS_URL')
    def validate_redis_url(cls, v):
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError('REDIS_URL must start with redis:// or rediss://')
        return v

    @validator('AUTH_SECRET')
    def validate_auth_secret(cls, v):
        if len(v) < 32:
            raise ValueError('AUTH_SECRET must be at least 32 characters long')
        return v

    @property
    def redis_settings(self) -> RedisSettings:
        """Get ARQ Redis settings - simplified version"""
        return RedisSettings.from_dsn(self.REDIS_URL)


# Global settings instance
settings = Settings()