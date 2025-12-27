"""Surgical edit tool for notes - exact string replacement."""

from .base import Tool, ToolResult


class EditNoteTool(Tool):
    """Surgical edit - exact string replacement in a note."""

    name = "edit_note"
    description = (
        "Make a surgical edit to a note using exact string replacement. "
        "IMPORTANT: You must read the note first before editing. "
        "The old_string must match EXACTLY (including whitespace and indentation). "
        "The edit will FAIL if old_string appears multiple times - provide more context "
        "to make it unique, or use replace_all=true to replace all occurrences."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to find and replace (must be unique in file unless replace_all=true)",
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with (must be different from old_string)",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace ALL occurrences instead of requiring unique match (default: false)",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }
    requires_confirmation = True

    def get_confirmation_message(
        self, path: str, old_string: str, new_string: str, replace_all: bool = False, **kwargs
    ) -> str:
        old_preview = old_string[:30] + "..." if len(old_string) > 30 else old_string
        new_preview = new_string[:30] + "..." if len(new_string) > 30 else new_string
        action = "Replace all" if replace_all else "Edit"
        return f"{action} '{path}': '{old_preview}' → '{new_preview}'"

    def execute(
        self, path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        # old_string and new_string must be different
        if old_string == new_string:
            return ToolResult(
                success=False,
                data=None,
                message="old_string and new_string must be different",
            )

        content = full_path.read_text(encoding="utf-8")

        # Count occurrences
        occurrence_count = content.count(old_string)

        if occurrence_count == 0:
            return ToolResult(
                success=False,
                data=None,
                message=f"Could not find text to replace in {path}. Make sure to read the note first and use the exact text.",
            )

        if occurrence_count > 1 and not replace_all:
            return ToolResult(
                success=False,
                data=None,
                message=(
                    f"Found {occurrence_count} occurrences of old_string in {path}. "
                    "Provide more surrounding context to make it unique, or set replace_all=true."
                ),
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced_count = occurrence_count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced_count = 1

        full_path.write_text(new_content, encoding="utf-8")

        # Create a short preview of what changed
        old_preview = old_string[:50] + "..." if len(old_string) > 50 else old_string
        new_preview = new_string[:50] + "..." if len(new_string) > 50 else new_string

        if replace_all and replaced_count > 1:
            message = f"Replaced {replaced_count} occurrences in {path}"
        else:
            message = f"Edited {path}: '{old_preview}' → '{new_preview}'"

        return ToolResult(
            success=True,
            data={"path": path, "old": old_string, "new": new_string, "count": replaced_count},
            message=message,
        )
