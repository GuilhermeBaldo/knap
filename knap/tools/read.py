"""Tools for reading and searching notes."""

import re
from typing import Literal

from .base import Tool, ToolResult


class ReadNoteTool(Tool):
    """Read the contents of a note with optional line range."""

    name = "read_note"
    description = (
        "Read the contents of a note by its path. Returns content with line numbers. "
        "Use offset and limit for large notes to read specific sections."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the note relative to vault root (e.g., 'folder/note.md' or 'note')",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed). Only provide for large notes.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of lines to read. Only provide for large notes.",
            },
        },
        "required": ["path"],
    }

    def execute(self, path: str, offset: int | None = None, limit: int | None = None) -> ToolResult:
        path = self._ensure_md_extension(path)
        full_path = self._validate_path(path)

        if not full_path.exists():
            return ToolResult(
                success=False,
                data=None,
                message=f"Note not found: {path}",
            )

        content = full_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        total_lines = len(lines)

        # Apply offset and limit if provided
        start_line = 1
        if offset is not None:
            start_line = max(1, offset)

        end_line = total_lines
        if limit is not None:
            end_line = min(total_lines, start_line + limit - 1)

        # Extract the requested lines (convert to 0-indexed for slicing)
        selected_lines = lines[start_line - 1 : end_line]

        # Format with line numbers (like cat -n)
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=start_line):
            formatted_lines.append(f"{i:6}\t{line}")

        formatted_content = "\n".join(formatted_lines)

        # Build message
        if offset is not None or limit is not None:
            message = f"Read note: {path} (lines {start_line}-{end_line} of {total_lines})"
        else:
            message = f"Read note: {path} ({total_lines} lines, {len(content)} chars)"

        return ToolResult(
            success=True,
            data=formatted_content,
            message=message,
        )


class GrepNotesTool(Tool):
    """Search note contents using regex patterns."""

    name = "grep_notes"
    description = (
        "Search for patterns across all notes using regex. Supports different output modes: "
        "'files_with_matches' (default) returns just file paths, 'content' returns matching lines "
        "with context, 'count' returns match counts per file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for (e.g., 'TODO', 'class\\s+\\w+', 'meeting|standup')",
            },
            "output_mode": {
                "type": "string",
                "enum": ["files_with_matches", "content", "count"],
                "description": "Output format: 'files_with_matches' (paths only), 'content' (matching lines), 'count' (match counts)",
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Case-insensitive search (default: true)",
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context before/after match (only for 'content' mode, default: 1)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of files to return (default: 20)",
            },
            "glob": {
                "type": "string",
                "description": "Optional glob pattern to filter which notes to search (e.g., 'Projects/**')",
            },
        },
        "required": ["pattern"],
    }

    def execute(
        self,
        pattern: str,
        output_mode: Literal["files_with_matches", "content", "count"] = "files_with_matches",
        case_insensitive: bool = True,
        context_lines: int = 1,
        max_results: int = 20,
        glob: str | None = None,
    ) -> ToolResult:
        import fnmatch

        # Compile regex
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(
                success=False,
                data=None,
                message=f"Invalid regex pattern: {e}",
            )

        results = []
        files_searched = 0

        for md_file in self.vault_path.rglob("*.md"):
            # Skip hidden folders
            try:
                rel_parts = md_file.relative_to(self.vault_path).parts
                if any(part.startswith(".") for part in rel_parts):
                    continue
            except ValueError:
                continue

            rel_path = str(md_file.relative_to(self.vault_path))

            # Apply glob filter if provided
            if glob and not fnmatch.fnmatch(rel_path, glob):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                files_searched += 1

                # Find all matches
                match_lines = []
                for line_num, line in enumerate(lines, 1):
                    if regex.search(line):
                        match_lines.append((line_num, line))

                if not match_lines:
                    continue

                if output_mode == "files_with_matches":
                    results.append(rel_path)

                elif output_mode == "count":
                    total_matches = sum(len(regex.findall(line)) for _, line in match_lines)
                    results.append({"path": rel_path, "count": total_matches})

                elif output_mode == "content":
                    # Build context for each match
                    file_matches = []
                    for line_num, _line in match_lines:
                        # Get context lines
                        context_start = max(0, line_num - 1 - context_lines)
                        context_end = min(len(lines), line_num + context_lines)

                        context_block = []
                        for ctx_num in range(context_start, context_end):
                            prefix = ">" if ctx_num == line_num - 1 else " "
                            context_block.append(f"{prefix}{ctx_num + 1:4}: {lines[ctx_num]}")

                        file_matches.append("\n".join(context_block))

                    results.append(
                        {
                            "path": rel_path,
                            "matches": file_matches[:5],  # Limit matches per file
                        }
                    )

                if len(results) >= max_results:
                    break

            except Exception:
                continue

        if not results:
            return ToolResult(
                success=True,
                data=[],
                message=f"No matches for pattern '{pattern}' in {files_searched} notes",
            )

        return ToolResult(
            success=True,
            data=results,
            message=f"Found matches in {len(results)} notes (searched {files_searched})",
        )


class SearchByTagTool(Tool):
    """Search notes by tag."""

    name = "search_by_tag"
    description = "Find all notes with a specific tag. Tags can be in frontmatter or inline (#tag)."
    parameters = {
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Tag to search for (with or without #)",
            },
        },
        "required": ["tag"],
    }

    def execute(self, tag: str) -> ToolResult:
        # Normalize tag (remove # if present)
        tag = tag.lstrip("#")
        results = []

        # Pattern for inline tags
        inline_pattern = re.compile(rf"#\b{re.escape(tag)}\b", re.IGNORECASE)

        # Pattern for frontmatter tags
        frontmatter_pattern = re.compile(
            rf"tags:\s*\[.*?\b{re.escape(tag)}\b.*?\]", re.IGNORECASE | re.DOTALL
        )

        for md_file in self.vault_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")

                if inline_pattern.search(content) or frontmatter_pattern.search(content):
                    rel_path = md_file.relative_to(self.vault_path)
                    results.append(str(rel_path))

            except Exception:
                continue

        if not results:
            return ToolResult(
                success=True,
                data=[],
                message=f"No notes found with tag '#{tag}'",
            )

        return ToolResult(
            success=True,
            data=results,
            message=f"Found {len(results)} notes with tag '#{tag}'",
        )
