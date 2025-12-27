"""Tests for config module."""

from pathlib import Path

import pytest

from knap.config import Settings


class TestSettings:
    """Tests for Settings class."""

    def test_allowed_users_single(self, tmp_vault: Path, monkeypatch):
        """Test parsing single user ID."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345")

        settings = Settings()
        assert settings.allowed_users == [12345]

    def test_allowed_users_multiple(self, tmp_vault: Path, monkeypatch):
        """Test parsing multiple user IDs."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345, 67890, 11111")

        settings = Settings()
        assert settings.allowed_users == [12345, 67890, 11111]

    def test_default_model(self, tmp_vault: Path, monkeypatch):
        """Test default OpenAI model."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345")
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        settings = Settings(_env_file=None)
        assert settings.openai_model == "gpt-5-nano"

    def test_custom_model(self, tmp_vault: Path, monkeypatch):
        """Test custom OpenAI model."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5-nano")

        settings = Settings()
        assert settings.openai_model == "gpt-5-nano"

    def test_vault_path_validation_not_exists(self, tmp_path: Path, monkeypatch):
        """Test vault path validation when path doesn't exist."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(tmp_path / "nonexistent"))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345")

        with pytest.raises(ValueError, match="does not exist"):
            Settings()

    def test_vault_path_validation_not_directory(self, tmp_path: Path, monkeypatch):
        """Test vault path validation when path is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.touch()

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("VAULT_PATH", str(file_path))
        monkeypatch.setenv("ALLOWED_USER_IDS", "12345")

        with pytest.raises(ValueError, match="not a directory"):
            Settings()
