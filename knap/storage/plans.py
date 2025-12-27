"""Plan storage for multi-step operations."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from knap.agent.planning import Plan, PlanStatus

logger = logging.getLogger(__name__)


class PlanStorage:
    """Manages plans stored in memory and disk."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path
        self.plans_file = vault_path / ".knap" / "plans.json"
        self._plans: dict[str, Plan] = {}
        self._load()

    def save(self, plan: Plan) -> None:
        """Save a plan (create or update)."""
        self._plans[plan.plan_id] = plan
        self._save()

    def get(self, plan_id: str) -> Plan | None:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def remove(self, plan_id: str) -> Plan | None:
        """Remove and return a plan."""
        plan = self._plans.pop(plan_id, None)
        if plan:
            self._save()
        return plan

    def get_for_user(self, user_id: int) -> list[Plan]:
        """Get all plans for a user."""
        return [p for p in self._plans.values() if p.user_id == user_id]

    def get_pending_for_user(self, user_id: int) -> Plan | None:
        """Get the pending plan for a user (awaiting approval)."""
        for plan in self._plans.values():
            if plan.user_id == user_id and plan.status == PlanStatus.PENDING:
                return plan
        return None

    def get_executing_for_user(self, user_id: int) -> Plan | None:
        """Get the currently executing plan for a user."""
        for plan in self._plans.values():
            if plan.user_id == user_id and plan.status in (
                PlanStatus.APPROVED,
                PlanStatus.EXECUTING,
            ):
                return plan
        return None

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Remove old completed/cancelled plans. Returns count removed."""
        now = datetime.now(UTC)
        to_remove = []

        for plan_id, plan in self._plans.items():
            if plan.status in (PlanStatus.COMPLETED, PlanStatus.CANCELLED):
                age_hours = (now - plan.created_at.replace(tzinfo=UTC)).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(plan_id)

        for plan_id in to_remove:
            del self._plans[plan_id]

        if to_remove:
            self._save()

        return len(to_remove)

    def _load(self) -> None:
        """Load plans from disk."""
        if not self.plans_file.exists():
            return

        try:
            data = json.loads(self.plans_file.read_text(encoding="utf-8"))
            self._plans = {pid: Plan.from_dict(p) for pid, p in data.items()}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load plans: {e}")
            self._plans = {}

    def _save(self) -> None:
        """Save plans to disk."""
        try:
            self.plans_file.parent.mkdir(parents=True, exist_ok=True)
            data = {pid: p.to_dict() for pid, p in self._plans.items()}
            self.plans_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save plans: {e}")
