"""Tools for managing Knap settings."""

from typing import Any

from knap.storage import SettingsStorage

from .base import Tool, ToolResult


class GetSettingsTool(Tool):
    """Get current Knap settings."""

    name = "get_settings"
    description = "Get current Knap settings. Use when user asks about their preferences."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, settings_storage: SettingsStorage) -> None:
        self.settings_storage = settings_storage
        # No vault_path needed, skip parent __init__

    def execute(self) -> ToolResult:
        settings = self.settings_storage.get()
        return ToolResult(
            success=True,
            data=settings.to_dict(),
            message="Current settings retrieved",
        )


class UpdateSettingsTool(Tool):
    """Update Knap settings."""

    name = "update_settings"
    description = (
        "Update Knap settings. Available settings: "
        "require_confirmations (bool) - whether to ask for confirmation before destructive actions, "
        "confirmation_timeout_minutes (int) - how long confirmations remain valid."
    )
    parameters = {
        "type": "object",
        "properties": {
            "require_confirmations": {
                "type": "boolean",
                "description": "Whether to require confirmation for destructive actions (create, edit, delete notes)",
            },
            "confirmation_timeout_minutes": {
                "type": "integer",
                "description": "How many minutes a confirmation remains valid",
            },
        },
        "required": [],
    }

    def __init__(self, settings_storage: SettingsStorage) -> None:
        self.settings_storage = settings_storage

    def execute(self, **kwargs: Any) -> ToolResult:
        if not kwargs:
            return ToolResult(
                success=False,
                data=None,
                message="No settings provided to update",
            )

        # Filter to valid settings only
        valid_keys = {"require_confirmations", "confirmation_timeout_minutes"}
        updates = {k: v for k, v in kwargs.items() if k in valid_keys}

        if not updates:
            return ToolResult(
                success=False,
                data=None,
                message=f"Invalid settings. Valid options: {', '.join(valid_keys)}",
            )

        settings = self.settings_storage.update(**updates)

        # Build confirmation message
        changes = ", ".join(f"{k}={v}" for k, v in updates.items())
        return ToolResult(
            success=True,
            data=settings.to_dict(),
            message=f"Settings updated: {changes}",
        )
