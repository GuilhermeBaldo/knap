"""Vault tools for interacting with Obsidian notes."""

from collections.abc import Callable
from pathlib import Path

from knap.storage import SettingsStorage

from .base import Tool, ToolRegistry, ToolResult
from .daily import GetDailyNoteTool
from .edit import EditNoteTool
from .frontmatter import GetFrontmatterTool, SetFrontmatterTool
from .glob import GlobNotesTool
from .index import RefreshVaultIndexTool
from .navigate import GetBacklinksTool, ListFolderTool
from .read import GrepNotesTool, ReadNoteTool, SearchByTagTool
from .settings import GetSettingsTool, UpdateSettingsTool
from .tasks import TodoWriteTool
from .web import WebSearchTool
from .write import AppendToNoteTool, CreateNoteTool, DeleteNoteTool, UpdateNoteTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "create_tool_registry",
]


def create_tool_registry(
    vault_path: Path,
    settings_storage: SettingsStorage,
    refresh_callback: Callable[[], None] | None = None,
    task_update_callback: Callable | None = None,
) -> ToolRegistry:
    """Create a registry with all available tools."""
    registry = ToolRegistry()

    # Search tools (Claude Code style: glob -> grep -> read)
    registry.register(GlobNotesTool(vault_path))
    registry.register(GrepNotesTool(vault_path))
    registry.register(ReadNoteTool(vault_path))
    registry.register(SearchByTagTool(vault_path))

    # Write tools
    registry.register(CreateNoteTool(vault_path))
    registry.register(UpdateNoteTool(vault_path))
    registry.register(AppendToNoteTool(vault_path))
    registry.register(DeleteNoteTool(vault_path))
    registry.register(EditNoteTool(vault_path))

    # Navigation tools
    registry.register(ListFolderTool(vault_path))
    registry.register(GetBacklinksTool(vault_path))

    # Frontmatter tools
    registry.register(GetFrontmatterTool(vault_path))
    registry.register(SetFrontmatterTool(vault_path))

    # Daily note tool
    registry.register(GetDailyNoteTool(vault_path))

    # Index tool
    refresh_tool = RefreshVaultIndexTool(vault_path)
    if refresh_callback:
        refresh_tool.set_rebuild_callback(refresh_callback)
    registry.register(refresh_tool)

    # Settings tools
    registry.register(GetSettingsTool(settings_storage))
    registry.register(UpdateSettingsTool(settings_storage))

    # Web tools
    registry.register(WebSearchTool())

    # Task tracking tool
    todo_tool = TodoWriteTool(vault_path)
    if task_update_callback:
        todo_tool.set_update_callback(task_update_callback)
    registry.register(todo_tool)

    return registry
