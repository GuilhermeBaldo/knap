"""Tool for refreshing the vault index."""

from pathlib import Path

from knap.indexer import VaultScanner

from .base import Tool, ToolResult


class RefreshVaultIndexTool(Tool):
    """Refresh the vault index to pick up new/changed notes."""

    name = "refresh_vault_index"
    description = (
        "Rebuild the vault index to reflect recent changes. "
        "Use this after creating, updating, or deleting notes, "
        "or when you need an updated view of the vault structure."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, vault_path: Path) -> None:
        super().__init__(vault_path)
        self._rebuild_callback: callable | None = None

    def set_rebuild_callback(self, callback: callable) -> None:
        """Set a callback to trigger index rebuild in the agent."""
        self._rebuild_callback = callback

    def execute(self) -> ToolResult:
        # Trigger rebuild through callback if set
        if self._rebuild_callback:
            self._rebuild_callback()
            return ToolResult(
                success=True,
                data=None,
                message="Vault index refreshed successfully.",
            )

        # Fallback: do a scan and report stats
        scanner = VaultScanner(self.vault_path)
        index = scanner.scan()

        return ToolResult(
            success=True,
            data={
                "total_notes": index.total_notes,
                "total_folders": len(index.folders),
                "total_tags": len(index.tags),
            },
            message=f"Scanned vault: {index.total_notes} notes, {len(index.folders)} folders, {len(index.tags)} tags.",
        )
