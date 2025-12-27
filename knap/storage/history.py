"""Persistent conversation history storage."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConversationHistory:
    """Persistent conversation history using JSON files."""

    def __init__(self, vault_path: Path, max_messages: int = 40) -> None:
        self.data_dir = vault_path / ".knap" / "conversations"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages = max_messages

        # In-memory cache
        self._cache: dict[int, list[dict[str, Any]]] = {}

    def _get_file_path(self, user_id: int) -> Path:
        """Get the file path for a user's history."""
        return self.data_dir / f"{user_id}.json"

    def _load_from_disk(self, user_id: int) -> list[dict[str, Any]]:
        """Load history from disk."""
        file_path = self._get_file_path(user_id)
        if not file_path.exists():
            return []

        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load history for user {user_id}: {e}")
            return []

    def _save_to_disk(self, user_id: int, history: list[dict[str, Any]]) -> None:
        """Save history to disk."""
        file_path = self._get_file_path(user_id)
        try:
            file_path.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save history for user {user_id}: {e}")

    def get(self, user_id: int) -> list[dict[str, Any]]:
        """Get conversation history for a user."""
        if user_id not in self._cache:
            self._cache[user_id] = self._load_from_disk(user_id)
        return self._cache[user_id]

    def add(self, user_id: int, message: dict[str, Any]) -> None:
        """Add a message to history."""
        history = self.get(user_id)
        history.append(message)

        # Trim if too long
        if len(history) > self.max_messages:
            history[:] = history[-self.max_messages :]

        self._save_to_disk(user_id, history)

    def clear(self, user_id: int) -> None:
        """Clear history for a user."""
        self._cache[user_id] = []
        file_path = self._get_file_path(user_id)
        if file_path.exists():
            file_path.unlink()
