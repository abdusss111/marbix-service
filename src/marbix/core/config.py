# core/config.py
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Database connection URL
    DATABASE_URL: str = Field(
        "postgresql://postgres:postgres@localhost/postgres",
        env="DATABASE_URL"
    )

    # JWT settings
    AUTH_SECRET: str = Field(
        "dev-secret-key",
        env="AUTH_SECRET"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        30, env="REFRESH_TOKEN_EXPIRE_DAYS"
    )


# single, application-wide settings instance
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

