"""Configuration management using pydantic-settings."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-5-nano"

    # Vault
    vault_path: Path

    # Security - stored as comma-separated string in .env
    allowed_user_ids: str

    @property
    def allowed_users(self) -> list[int]:
        """Parse allowed user IDs as list of integers."""
        return [int(uid.strip()) for uid in self.allowed_user_ids.split(",") if uid.strip()]

    @field_validator("vault_path")
    @classmethod
    def validate_vault_path(cls, v: Path) -> Path:
        """Ensure vault path exists and is a directory."""
        if not v.exists():
            raise ValueError(f"Vault path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Vault path is not a directory: {v}")
        return v.resolve()


def get_settings() -> Settings:
    """Load settings from environment."""
    return Settings()
