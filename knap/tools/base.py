"""Base tool class and registry for vault operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    data: Any
    message: str


class Tool(ABC):
    """Base class for vault tools."""

    name: str
    description: str
    parameters: dict[str, Any]
    requires_confirmation: bool = False

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path

    def get_confirmation_message(self, **kwargs) -> str:
        """Get a human-readable confirmation message. Override for custom messages."""
        return f"Execute {self.name}?"

    def _validate_path(self, path: str) -> Path:
        """Validate that path is within vault and return resolved path."""
        # Normalize the path
        if path.startswith("/"):
            path = path[1:]

        full_path = (self.vault_path / path).resolve()

        # Security check: ensure path is within vault
        try:
            full_path.relative_to(self.vault_path)
        except ValueError as e:
            raise ValueError(f"Path escapes vault: {path}") from e

        return full_path

    def _ensure_md_extension(self, path: str) -> str:
        """Add .md extension if not present."""
        if not path.endswith(".md"):
            return path + ".md"
        return path

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def to_openai_function(self) -> dict:
        """Convert tool to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolRegistry:
    """Registry of available tools."""

    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self.tools.get(name)

    def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                message=f"Unknown tool: {name}",
            )
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                message=f"Tool error: {e}",
            )

    def get_openai_tools(self) -> list[dict]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_function() for tool in self.tools.values()]
