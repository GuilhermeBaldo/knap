"""Task tracking for multi-step agent operations."""

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Task:
    """A single task in the agent's task list."""

    content: str  # Imperative form: "Read shopping list"
    active_form: str  # Present continuous: "Reading shopping list"
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "content": self.content,
            "active_form": self.active_form,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create from dictionary."""
        return cls(
            content=data["content"],
            active_form=data["active_form"],
            status=TaskStatus(data["status"]),
        )


@dataclass
class TaskList:
    """List of tasks for tracking agent progress."""

    user_id: int
    tasks: list[Task] = field(default_factory=list)

    def add(self, content: str, active_form: str) -> Task:
        """Add a new task."""
        task = Task(content=content, active_form=active_form)
        self.tasks.append(task)
        return task

    def set_in_progress(self, index: int) -> None:
        """Mark a task as in progress."""
        if 0 <= index < len(self.tasks):
            self.tasks[index].status = TaskStatus.IN_PROGRESS

    def complete(self, index: int) -> None:
        """Mark a task as completed."""
        if 0 <= index < len(self.tasks):
            self.tasks[index].status = TaskStatus.COMPLETED

    def clear(self) -> None:
        """Clear all tasks."""
        self.tasks = []

    def update_all(self, tasks: list[Task]) -> None:
        """Replace all tasks with new list."""
        self.tasks = tasks

    def to_log_lines(self) -> list[str]:
        """Format tasks for terminal logging."""
        lines = []
        for task in self.tasks:
            if task.status == TaskStatus.COMPLETED:
                prefix = "[x]"
            elif task.status == TaskStatus.IN_PROGRESS:
                prefix = "[>]"
            else:
                prefix = "[ ]"

            # Use active_form for in_progress, content otherwise
            if task.status == TaskStatus.IN_PROGRESS:
                text = task.active_form
            else:
                text = task.content

            lines.append(f"{prefix} {text}")
        return lines

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskList":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
        )
