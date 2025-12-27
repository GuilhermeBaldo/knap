"""Tools for working with YAML frontmatter."""

import re
from typing import Any

import yaml

from .base import Tool, ToolResult


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse frontmatter from note content.

    Returns (frontmatter_dict, body_content).
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
        body = match.group(2)
        return frontmatter, body
    except yaml.YAMLError:
        return {}, content


def serialize_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    """Combine frontmatter and body into note content."""
    if not frontmatter:
        return body

    fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    return f"---\n{fm_str}---\n{body}"


class GetFrontmatterTool(Tool):
    """Read frontmatter from a note."""

    name = "get_frontmatter"
    description = "Read the YAML frontmatter (metadata) from a note."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note",
            },
        },
        "required": ["path"],
    }

    def execute(self, path: str) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        content = full_path.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(content)

        if not frontmatter:
            return ToolResult(
                success=True,
                data={},
                message=f"Note '{path}' has no frontmatter",
            )

        return ToolResult(
            success=True,
            data=frontmatter,
            message=f"Frontmatter from '{path}'",
        )


class SetFrontmatterTool(Tool):
    """Update frontmatter in a note."""

    name = "set_frontmatter"
    description = (
        "Update or add frontmatter fields in a note. Existing fields not specified are preserved."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note",
            },
            "frontmatter": {
                "type": "object",
                "description": "Frontmatter fields to set/update",
            },
        },
        "required": ["path", "frontmatter"],
    }
    requires_confirmation = True

    def get_confirmation_message(self, path: str, frontmatter: dict, **kwargs) -> str:
        fields = ", ".join(frontmatter.keys())
        return f"Update frontmatter in '{path}': {fields}"

    def execute(self, path: str, frontmatter: dict[str, Any]) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        content = full_path.read_text(encoding="utf-8")
        existing_fm, body = parse_frontmatter(content)

        # Merge frontmatter (new values override existing)
        existing_fm.update(frontmatter)

        # Write back
        new_content = serialize_frontmatter(existing_fm, body)
        full_path.write_text(new_content, encoding="utf-8")

        return ToolResult(
            success=True,
            data=existing_fm,
            message=f"Updated frontmatter in '{path}'",
        )
