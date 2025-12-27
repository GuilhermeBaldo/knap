"""Tools for navigating the vault structure."""

import re

from .base import Tool, ToolResult


class ListFolderTool(Tool):
    """List contents of a folder."""

    name = "list_folder"
    description = "List all notes and subfolders in a directory. Use '/' or '' for vault root."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Folder path relative to vault root (use '/' for root)",
            },
        },
        "required": ["path"],
    }

    def execute(self, path: str = "/") -> ToolResult:
        # Handle root path
        if path in ("/", ""):
            folder_path = self.vault_path
        else:
            folder_path = self._validate_path(path)

        if not folder_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Folder not found: {path}",
            )

        if not folder_path.is_dir():
            return ToolResult(
                success=False,
                data=None,
                message=f"Not a folder: {path}",
            )

        items = {"folders": [], "notes": []}

        for item in sorted(folder_path.iterdir()):
            # Skip hidden files/folders
            if item.name.startswith("."):
                continue

            rel_path = item.relative_to(self.vault_path)

            if item.is_dir():
                items["folders"].append(str(rel_path))
            elif item.suffix == ".md":
                # Get note title from first heading or filename
                title = item.stem
                try:
                    content = item.read_text(encoding="utf-8")
                    # Look for first h1 heading
                    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    if match:
                        title = match.group(1)
                except Exception:
                    pass

                items["notes"].append({"path": str(rel_path), "title": title})

        return ToolResult(
            success=True,
            data=items,
            message=f"Found {len(items['folders'])} folders and {len(items['notes'])} notes in '{path}'",
        )


class GetBacklinksTool(Tool):
    """Find notes that link to a specific note."""

    name = "get_backlinks"
    description = "Find all notes that contain wikilinks to the specified note."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note to find backlinks for",
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

        # Get the note name without extension for wikilink matching
        note_name = full_path.stem

        # Pattern for wikilinks: [[note]] or [[note|alias]] or [[folder/note]]
        pattern = re.compile(
            rf"\[\[(?:[^|\]]*[/\\])?{re.escape(note_name)}(?:\|[^\]]+)?\]\]",
            re.IGNORECASE,
        )

        backlinks = []

        for md_file in self.vault_path.rglob("*.md"):
            # Skip the note itself
            if md_file == full_path:
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                if pattern.search(content):
                    rel_path = md_file.relative_to(self.vault_path)
                    backlinks.append(str(rel_path))
            except Exception:
                continue

        return ToolResult(
            success=True,
            data=backlinks,
            message=f"Found {len(backlinks)} notes linking to '{note_name}'",
        )
