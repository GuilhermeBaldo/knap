"""User settings and pending confirmation storage."""

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserSettings:
    """User-configurable settings for Knap."""

    require_confirmations: bool = True
    confirmation_timeout_minutes: int = 5

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserSettings":
        return cls(
            require_confirmations=data.get("require_confirmations", True),
            confirmation_timeout_minutes=data.get("confirmation_timeout_minutes", 5),
        )


class SettingsStorage:
    """Manages user settings stored in .knap/settings.json."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path
        self.knap_dir = vault_path / ".knap"
        self.settings_file = self.knap_dir / "settings.json"
        self._settings: UserSettings | None = None

    def get(self) -> UserSettings:
        """Get current settings, loading from disk or creating defaults."""
        if self._settings is None:
            self._settings = self._load()
        return self._settings

    def update(self, **kwargs) -> UserSettings:
        """Update specific settings and save to disk."""
        settings = self.get()

        # Update only provided fields
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        self._save(settings)
        self._settings = settings
        return settings

    def _load(self) -> UserSettings:
        """Load settings from disk, creating defaults if missing."""
        if not self.settings_file.exists():
            settings = UserSettings()
            self._save(settings)
            return settings

        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            return UserSettings.from_dict(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load settings, using defaults: {e}")
            return UserSettings()

    def _save(self, settings: UserSettings) -> None:
        """Save settings to disk."""
        try:
            self.knap_dir.mkdir(parents=True, exist_ok=True)
            self.settings_file.write_text(
                json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save settings: {e}")


@dataclass
class PendingConfirmation:
    """A tool call awaiting user confirmation."""

    confirmation_id: str
    user_id: int
    tool_name: str
    tool_args: dict[str, Any]
    message: str  # Human-readable description of the action
    created_at: str  # ISO format timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PendingConfirmation":
        return cls(**data)

    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if this confirmation has expired."""
        created = datetime.fromisoformat(self.created_at)
        now = datetime.now(UTC)
        age_minutes = (now - created).total_seconds() / 60
        return age_minutes > timeout_minutes


class PendingConfirmationStorage:
    """Manages pending confirmations stored in memory and disk."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path
        self.pending_file = vault_path / ".knap" / "pending_confirmations.json"
        self._pending: dict[str, PendingConfirmation] = {}
        self._load()

    def create(
        self,
        user_id: int,
        tool_name: str,
        tool_args: dict[str, Any],
        message: str,
    ) -> PendingConfirmation:
        """Create a new pending confirmation."""
        confirmation = PendingConfirmation(
            confirmation_id=str(uuid.uuid4())[:8],
            user_id=user_id,
            tool_name=tool_name,
            tool_args=tool_args,
            message=message,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._pending[confirmation.confirmation_id] = confirmation
        self._save()
        return confirmation

    def get(self, confirmation_id: str) -> PendingConfirmation | None:
        """Get a pending confirmation by ID."""
        return self._pending.get(confirmation_id)

    def remove(self, confirmation_id: str) -> PendingConfirmation | None:
        """Remove and return a pending confirmation."""
        confirmation = self._pending.pop(confirmation_id, None)
        if confirmation:
            self._save()
        return confirmation

    def get_for_user(self, user_id: int) -> list[PendingConfirmation]:
        """Get all pending confirmations for a user."""
        return [c for c in self._pending.values() if c.user_id == user_id]

    def cleanup_expired(self, timeout_minutes: int) -> int:
        """Remove expired confirmations. Returns count removed."""
        expired = [cid for cid, c in self._pending.items() if c.is_expired(timeout_minutes)]
        for cid in expired:
            del self._pending[cid]
        if expired:
            self._save()
        return len(expired)

    def _load(self) -> None:
        """Load pending confirmations from disk."""
        if not self.pending_file.exists():
            return

        try:
            data = json.loads(self.pending_file.read_text(encoding="utf-8"))
            self._pending = {cid: PendingConfirmation.from_dict(c) for cid, c in data.items()}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load pending confirmations: {e}")
            self._pending = {}

    def _save(self) -> None:
        """Save pending confirmations to disk."""
        try:
            self.pending_file.parent.mkdir(parents=True, exist_ok=True)
            data = {cid: c.to_dict() for cid, c in self._pending.items()}
            self.pending_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save pending confirmations: {e}")
