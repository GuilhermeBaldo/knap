"""Planning system for complex multi-step operations."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    """Status of a plan."""

    PENDING = "pending"  # Awaiting user approval
    APPROVED = "approved"  # User approved, ready to execute
    EXECUTING = "executing"  # Currently executing
    COMPLETED = "completed"  # All steps completed
    CANCELLED = "cancelled"  # User cancelled


class StepStatus(str, Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in a plan."""

    step_number: int
    description: str
    tool_name: str | None = None  # Which tool to use (optional, may be reasoning step)
    tool_args: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: str | None = None  # Result message after execution

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "status": self.status.value,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            step_number=data["step_number"],
            description=data["description"],
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args", {}),
            status=StepStatus(data.get("status", "pending")),
            result=data.get("result"),
        )


@dataclass
class Plan:
    """A multi-step plan for complex operations."""

    plan_id: str
    user_id: int
    title: str
    description: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        user_id: int,
        title: str,
        description: str,
        steps: list[PlanStep],
    ) -> "Plan":
        """Create a new plan with a unique ID."""
        return cls(
            plan_id=str(uuid.uuid4())[:8],
            user_id=user_id,
            title=title,
            description=description,
            steps=steps,
        )

    def approve(self) -> None:
        """Mark plan as approved."""
        self.status = PlanStatus.APPROVED

    def start_execution(self) -> None:
        """Mark plan as executing."""
        self.status = PlanStatus.EXECUTING

    def complete(self) -> None:
        """Mark plan as completed."""
        self.status = PlanStatus.COMPLETED

    def cancel(self) -> None:
        """Cancel the plan."""
        self.status = PlanStatus.CANCELLED

    def get_current_step(self) -> PlanStep | None:
        """Get the current step being executed."""
        for step in self.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        return None

    def get_next_step(self) -> PlanStep | None:
        """Get the next pending step."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def mark_step_in_progress(self, step_number: int) -> None:
        """Mark a step as in progress."""
        for step in self.steps:
            if step.step_number == step_number:
                step.status = StepStatus.IN_PROGRESS
                break

    def mark_step_completed(self, step_number: int, result: str = "") -> None:
        """Mark a step as completed."""
        for step in self.steps:
            if step.step_number == step_number:
                step.status = StepStatus.COMPLETED
                step.result = result
                break

    def mark_step_failed(self, step_number: int, error: str = "") -> None:
        """Mark a step as failed."""
        for step in self.steps:
            if step.step_number == step_number:
                step.status = StepStatus.FAILED
                step.result = error
                break

    @property
    def is_complete(self) -> bool:
        """Check if all steps are completed or failed."""
        return all(
            step.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)
            for step in self.steps
        )

    @property
    def progress(self) -> tuple[int, int]:
        """Return (completed_count, total_count)."""
        completed = sum(1 for step in self.steps if step.status == StepStatus.COMPLETED)
        return (completed, len(self.steps))

    def to_telegram_text(self, max_length: int = 4000) -> str:
        """Format plan for Telegram display."""
        lines = [f"**{self.title}**", "", self.description, ""]

        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                icon = "[x]"
            elif step.status == StepStatus.IN_PROGRESS:
                icon = "[>]"
            elif step.status == StepStatus.FAILED:
                icon = "[!]"
            else:
                icon = "[ ]"

            step_line = f"{icon} {step.step_number}. {step.description}"
            lines.append(step_line)

        text = "\n".join(lines)

        # Truncate if too long
        if len(text) > max_length:
            text = text[: max_length - 20] + "\n\n... (truncated)"

        return text

    def to_log_lines(self) -> list[str]:
        """Format plan for terminal logging."""
        lines = [f"Plan: {self.title} [{self.status.value}]"]
        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                prefix = "[x]"
            elif step.status == StepStatus.IN_PROGRESS:
                prefix = "[>]"
            elif step.status == StepStatus.FAILED:
                prefix = "[!]"
            else:
                prefix = "[ ]"

            tool_info = f" -> {step.tool_name}" if step.tool_name else ""
            lines.append(f"  {prefix} {step.step_number}. {step.description}{tool_info}")
        return lines

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_id": self.plan_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        """Create from dictionary."""
        return cls(
            plan_id=data["plan_id"],
            user_id=data["user_id"],
            title=data["title"],
            description=data["description"],
            steps=[PlanStep.from_dict(s) for s in data["steps"]],
            status=PlanStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
