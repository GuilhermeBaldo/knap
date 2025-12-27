"""Glob tool for fast pattern matching on note paths."""

import fnmatch

from .base import Tool, ToolResult


class GlobNotesTool(Tool):
    """Find notes by path pattern matching."""

    name = "glob_notes"
    description = (
        "Fast pattern matching to find notes by path. Use glob patterns like "
        "'**/*.md' for all notes, 'Projects/**' for a folder, or '*meeting*' for "
        "names containing 'meeting'. Returns paths sorted by modification time (newest first)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": (
                    "Glob pattern to match. Examples: '**/*.md' (all notes), "
                    "'Projects/**' (notes in Projects folder), '*todo*' (notes with 'todo' in name), "
                    "'*.md' (notes in root only)"
                ),
            },
            "path": {
                "type": "string",
                "description": "Optional folder to search in (relative to vault root). If not specified, searches entire vault.",
            },
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = "") -> ToolResult:
        # Determine search root
        if path:
            search_root = self._validate_path(path)
            if not search_root.is_dir():
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Path is not a directory: {path}",
                )
        else:
            search_root = self.vault_path

        # Find all markdown files
        all_files = []
        for md_file in search_root.rglob("*.md"):
            # Skip hidden folders
            if any(part.startswith(".") for part in md_file.relative_to(self.vault_path).parts):
                continue
            all_files.append(md_file)

        # Apply glob pattern matching
        matching_files = []
        for md_file in all_files:
            rel_path = str(md_file.relative_to(self.vault_path))
            # Match against the pattern (case-insensitive)
            # Handle ** pattern specially to also match root files
            pattern_lower = pattern.lower()
            rel_path_lower = rel_path.lower()

            matches = fnmatch.fnmatch(rel_path_lower, pattern_lower)

            # Special case: **/*.md should also match root-level files
            if not matches and pattern.startswith("**/"):
                # Try matching without the **/ prefix
                root_pattern = pattern[3:]
                matches = fnmatch.fnmatch(rel_path_lower, root_pattern.lower())

            if matches:
                matching_files.append((md_file, md_file.stat().st_mtime))

        # Sort by modification time (newest first)
        matching_files.sort(key=lambda x: -x[1])

        # Extract just the paths
        results = [str(f.relative_to(self.vault_path)) for f, _ in matching_files]

        if not results:
            return ToolResult(
                success=True,
                data=[],
                message=f"No notes found matching pattern '{pattern}'",
            )

        return ToolResult(
            success=True,
            data=results,
            message=f"Found {len(results)} notes matching '{pattern}'",
        )
