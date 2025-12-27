"""Tools for daily notes."""

from datetime import datetime

from .base import Tool, ToolResult


class GetDailyNoteTool(Tool):
    """Get or create today's daily note."""

    name = "get_daily_note"
    description = "Get today's daily note. Creates it if it doesn't exist."
    parameters = {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format (default: today)",
            },
            "folder": {
                "type": "string",
                "description": "Folder for daily notes (default: 'Daily Notes')",
            },
        },
        "required": [],
    }

    def execute(self, date: str | None = None, folder: str = "Daily Notes") -> ToolResult:
        # Parse date or use today
        if date:
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Invalid date format: {date}. Use YYYY-MM-DD.",
                )
        else:
            dt = datetime.now()

        # Format the note path
        date_str = dt.strftime("%Y-%m-%d")
        note_path = f"{folder}/{date_str}.md"

        full_path = self._validate_path(note_path)

        created = False
        if not full_path.exists():
            # Create the daily note with template
            full_path.parent.mkdir(parents=True, exist_ok=True)

            template = f"""---
date: {date_str}
tags: [daily]
---

## Tasks

- [ ]

## Notes

"""
            full_path.write_text(template, encoding="utf-8")
            created = True

        content = full_path.read_text(encoding="utf-8")

        return ToolResult(
            success=True,
            data={"path": note_path, "content": content, "created": created},
            message=f"{'Created' if created else 'Retrieved'} daily note: {note_path}",
        )
