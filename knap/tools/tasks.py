"""Task tracking tool for multi-step operations."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from knap.agent.tasks import Task, TaskStatus

from .base import Tool, ToolResult


class TodoWriteTool(Tool):
    """Tool for creating and managing task lists during multi-step operations."""

    name = "todo_write"
    description = (
        "Create or update a task list for tracking multi-step operations. "
        "Use this when handling complex requests that require multiple steps. "
        "Each task needs a content (imperative form like 'Read note') and "
        "active_form (present continuous like 'Reading note'). "
        "Set status to 'in_progress' when starting a task and 'completed' when done."
    )
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "List of tasks to track",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task in imperative form (e.g., 'Read shopping list')",
                        },
                        "active_form": {
                            "type": "string",
                            "description": "Task in present continuous form (e.g., 'Reading shopping list')",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Task status",
                        },
                    },
                    "required": ["content", "active_form", "status"],
                },
            },
        },
        "required": ["todos"],
    }

    def __init__(self, vault_path: Path) -> None:
        super().__init__(vault_path)
        self._update_callback: Callable[[list[Task]], None] | None = None

    def set_update_callback(self, callback: Callable[[list[Task]], None]) -> None:
        """Set a callback to update the task list in the agent."""
        self._update_callback = callback

    def execute(self, todos: list[dict[str, Any]]) -> ToolResult:
        # Convert dicts to Task objects
        tasks = []
        for todo in todos:
            task = Task(
                content=todo["content"],
                active_form=todo["active_form"],
                status=TaskStatus(todo["status"]),
            )
            tasks.append(task)

        # Update via callback if set
        if self._update_callback:
            self._update_callback(tasks)

        # Count by status
        pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)

        return ToolResult(
            success=True,
            data={
                "total": len(tasks),
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
            },
            message=f"Task list updated: {completed}/{len(tasks)} completed",
        )
