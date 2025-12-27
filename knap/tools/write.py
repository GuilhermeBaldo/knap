"""Tools for creating and modifying notes."""

from .base import Tool, ToolResult


class CreateNoteTool(Tool):
    """Create a new note."""

    name = "create_note"
    description = (
        "Create a new note at the specified path. Will fail if note already exists. "
        "Do NOT include an H1 title - the filename is the title in Obsidian."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path for the new note relative to vault root",
            },
            "content": {
                "type": "string",
                "description": "Content of the note (markdown)",
            },
        },
        "required": ["path", "content"],
    }
    requires_confirmation = True

    def get_confirmation_message(self, path: str, **kwargs) -> str:
        return f"Create note '{path}'?"

    def execute(self, path: str, content: str) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note already exists: {path}. Use update_note to modify it.",
            )

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            data={"path": path},
            message=f"Created note: {path}",
        )


class UpdateNoteTool(Tool):
    """Update an existing note's content."""

    name = "update_note"
    description = "Replace the entire content of an existing note. Use read_note first to see current content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note relative to vault root",
            },
            "content": {
                "type": "string",
                "description": "New content for the note (replaces existing)",
            },
        },
        "required": ["path", "content"],
    }
    requires_confirmation = True

    def get_confirmation_message(self, path: str, **kwargs) -> str:
        return f"Replace content of '{path}'?"

    def execute(self, path: str, content: str) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}. Use create_note to create it.",
            )

        full_path.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            data={"path": path},
            message=f"Updated note: {path}",
        )


class AppendToNoteTool(Tool):
    """Append content to the end of a note."""

    name = "append_to_note"
    description = "Add content to the end of an existing note."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note relative to vault root",
            },
            "content": {
                "type": "string",
                "description": "Content to append",
            },
        },
        "required": ["path", "content"],
    }
    requires_confirmation = True

    def get_confirmation_message(self, path: str, content: str, **kwargs) -> str:
        preview = content[:50] + "..." if len(content) > 50 else content
        return f"Append to '{path}': {preview}"

    def execute(self, path: str, content: str) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        existing = full_path.read_text(encoding="utf-8")
        # Ensure there's a newline between existing and new content
        if existing and not existing.endswith("\n"):
            content = "\n" + content

        full_path.write_text(existing + content, encoding="utf-8")
        return ToolResult(
            success=True,
            data={"path": path},
            message=f"Appended to note: {path}",
        )


class DeleteNoteTool(Tool):
    """Delete a note."""

    name = "delete_note"
    description = "Permanently delete a note. This cannot be undone."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note to delete",
            },
        },
        "required": ["path"],
    }
    requires_confirmation = True

    def get_confirmation_message(self, path: str, **kwargs) -> str:
        return f"Delete '{path}'? This cannot be undone."

    def execute(self, path: str) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        full_path.unlink()
        return ToolResult(
            success=True,
            data={"path": path},
            message=f"Deleted note: {path}",
        )
