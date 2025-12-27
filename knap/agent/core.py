"""Agent core - agentic loop with OpenAI function calling."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from knap.config import Settings
from knap.indexer import generate_vault_summary
from knap.storage import (
    ConversationHistory,
    PendingConfirmation,
    PendingConfirmationStorage,
    PlanStorage,
    SettingsStorage,
    VaultIndexStorage,
)
from knap.tools import create_tool_registry

from .planning import Plan, PlanStatus, PlanStep
from .prompts import PLANNING_PROMPT, SYSTEM_PROMPT
from .tasks import Task, TaskList

logger = logging.getLogger(__name__)


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"


# Name of the user guidelines note in the vault
KNAP_NOTE_NAME = "KNAP.md"

# Maximum number of tool calls in a single turn
MAX_TOOL_CALLS = 20


@dataclass
class ProgressUpdate:
    """Progress update during agent processing."""

    reasoning: str | None = None  # Current reasoning/thinking
    tool_name: str | None = None  # Tool being called
    tool_args: str | None = None  # Formatted tool arguments
    tool_result: str | None = None  # Tool result summary
    tasks: list[dict] | None = None  # Current task list
    is_final: bool = False  # True when processing is complete


@dataclass
class AgentResponse:
    """Response from the agent, including any pending confirmations."""

    text: str
    pending_confirmations: list[PendingConfirmation] = field(default_factory=list)
    pending_plan: Plan | None = None  # Plan awaiting user approval


class Agent:
    """AI agent that uses tools to interact with the Obsidian vault."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.history = ConversationHistory(settings.vault_path)
        self.vault_index = VaultIndexStorage(settings.vault_path, openai_client=self.client)
        self.user_settings = SettingsStorage(settings.vault_path)
        self.pending_confirmations = PendingConfirmationStorage(settings.vault_path)
        self.plans = PlanStorage(settings.vault_path)

        # Task tracking per user
        self.task_lists: dict[int, TaskList] = {}
        self._current_user_id: int | None = None  # Set during message processing

        # Create tools with callbacks
        self.tools = create_tool_registry(
            settings.vault_path,
            settings_storage=self.user_settings,
            refresh_callback=self.refresh_index,
            task_update_callback=self._update_tasks,
        )

    def clear_history(self, user_id: int) -> None:
        """Clear conversation history for a user."""
        self.history.clear(user_id)

    def _get_user_guidelines(self) -> str | None:
        """Read custom user guidelines from KNAP.md in vault root."""
        shard_note = self.settings.vault_path / KNAP_NOTE_NAME
        if not shard_note.exists():
            return None

        try:
            content = shard_note.read_text(encoding="utf-8")
            # Strip frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            return content
        except Exception as e:
            logger.warning(f"{Colors.YELLOW}Failed to read {KNAP_NOTE_NAME}: {e}{Colors.RESET}")
            return None

    def _build_messages(self, user_id: int) -> list[dict[str, Any]]:
        """Build messages array for API call."""
        # Get vault index and generate summary
        index = self.vault_index.get_index()
        vault_summary = generate_vault_summary(index)

        # Get user guidelines from KNAP.md
        user_guidelines = self._get_user_guidelines()

        # Combine system prompt with vault context and user guidelines
        full_prompt = SYSTEM_PROMPT

        # Add current datetime
        now = datetime.now()
        full_prompt += f"\n\n## Current Date and Time\n\n{now.strftime('%A, %B %d, %Y at %H:%M')}"

        if user_guidelines:
            full_prompt += f"\n\n## User Guidelines\n\n{user_guidelines}"

        full_prompt += f"\n\n{vault_summary}"

        messages = [{"role": "system", "content": full_prompt}]
        messages.extend(self.history.get(user_id))
        return messages

    def refresh_index(self) -> None:
        """Force a refresh of the vault index."""
        self.vault_index.rebuild()

    def _update_tasks(self, tasks: list[Task]) -> None:
        """Update task list for current user (called by todo_write tool)."""
        if self._current_user_id is None:
            return

        user_id = self._current_user_id
        if user_id not in self.task_lists:
            self.task_lists[user_id] = TaskList(user_id=user_id)

        self.task_lists[user_id].update_all(tasks)
        self._log_tasks(user_id)

    def _log_tasks(self, user_id: int) -> None:
        """Log the current task list to terminal."""
        task_list = self.task_lists.get(user_id)
        if not task_list or not task_list.tasks:
            return

        logger.info(f"{Colors.DIM}{'─' * 30}{Colors.RESET}")
        logger.info(f"{Colors.BOLD}{Colors.CYAN}Tasks:{Colors.RESET}")
        for line in task_list.to_log_lines():
            # Color based on status prefix
            if line.startswith("[x]"):
                logger.info(f"  {Colors.GREEN}{line}{Colors.RESET}")
            elif line.startswith("[>]"):
                logger.info(f"  {Colors.YELLOW}{line}{Colors.RESET}")
            else:
                logger.info(f"  {Colors.DIM}{line}{Colors.RESET}")
        logger.info(f"{Colors.DIM}{'─' * 30}{Colors.RESET}")

    # ─────────────────────────────────────────────────────────────────────────
    # Plan Mode Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _is_plan_request(self, message: str) -> bool:
        """Check if the user is explicitly requesting a plan."""
        message_lower = message.lower()
        plan_keywords = [
            "make a plan",
            "create a plan",
            "plan this",
            "faz um plano",
            "cria um plano",
            "planeje",
            "planeja",
        ]
        return any(keyword in message_lower for keyword in plan_keywords)

    def _parse_plan_response(self, response: str, user_id: int) -> Plan | None:
        """Parse LLM response into a Plan object."""
        import re

        # Extract title
        title_match = re.search(r"##\s*Plan:\s*(.+)", response)
        if not title_match:
            return None
        title = title_match.group(1).strip()

        # Extract description (text between title and ### Steps:)
        desc_match = re.search(r"##\s*Plan:.+\n\n(.+?)(?=###\s*Steps:)", response, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""

        # Extract steps
        steps_section = re.search(r"###\s*Steps:\s*\n([\s\S]+?)(?=###|$)", response)
        if not steps_section:
            return None

        steps = []
        step_pattern = re.compile(r"(\d+)\.\s*(.+?)(?:\s*-\s*Tool:\s*(\w+))?$", re.MULTILINE)
        for match in step_pattern.finditer(steps_section.group(1)):
            step_num = int(match.group(1))
            step_desc = match.group(2).strip()
            tool_name = match.group(3).strip() if match.group(3) else None

            steps.append(
                PlanStep(
                    step_number=step_num,
                    description=step_desc,
                    tool_name=tool_name,
                )
            )

        if not steps:
            return None

        return Plan.create(
            user_id=user_id,
            title=title,
            description=description,
            steps=steps,
        )

    async def _create_plan(self, user_id: int, message: str) -> Plan | None:
        """Create a plan from user request."""
        logger.info(f"{Colors.CYAN}Creating plan for request...{Colors.RESET}")

        # Get vault context
        index = self.vault_index.get_index()
        from knap.indexer import generate_compact_summary

        vault_summary = generate_compact_summary(index)

        messages = [
            {"role": "system", "content": PLANNING_PROMPT + "\n\n" + vault_summary},
            {"role": "user", "content": message},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        plan_text = response.choices[0].message.content or ""
        logger.info(f"{Colors.DIM}{plan_text}{Colors.RESET}")

        plan = self._parse_plan_response(plan_text, user_id)
        if plan:
            self.plans.save(plan)
            self._log_plan(plan)
        return plan

    def _log_plan(self, plan: Plan) -> None:
        """Log the current plan to terminal."""
        logger.info(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
        for line in plan.to_log_lines():
            if "[x]" in line:
                logger.info(f"{Colors.GREEN}{line}{Colors.RESET}")
            elif "[>]" in line:
                logger.info(f"{Colors.YELLOW}{line}{Colors.RESET}")
            elif "[!]" in line:
                logger.info(f"{Colors.RED}{line}{Colors.RESET}")
            else:
                logger.info(f"{Colors.DIM}{line}{Colors.RESET}")
        logger.info(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")

    def approve_plan(self, plan_id: str) -> Plan | None:
        """Approve a pending plan. Returns the plan or None if not found."""
        plan = self.plans.get(plan_id)
        if not plan or plan.status != PlanStatus.PENDING:
            return None

        plan.approve()
        self.plans.save(plan)
        logger.info(f"{Colors.GREEN}Plan approved: {plan.title}{Colors.RESET}")
        return plan

    def reject_plan(self, plan_id: str) -> Plan | None:
        """Reject a pending plan. Returns the plan or None if not found."""
        plan = self.plans.get(plan_id)
        if not plan or plan.status != PlanStatus.PENDING:
            return None

        plan.cancel()
        self.plans.save(plan)
        logger.info(f"{Colors.RED}Plan rejected: {plan.title}{Colors.RESET}")
        return plan

    async def execute_plan(self, plan: Plan) -> AgentResponse:
        """Execute an approved plan step by step."""
        plan.start_execution()
        self.plans.save(plan)

        logger.info(f"{Colors.CYAN}Executing plan: {plan.title}{Colors.RESET}")

        results = []
        for step in plan.steps:
            plan.mark_step_in_progress(step.step_number)
            self.plans.save(plan)
            self._log_plan(plan)

            if step.tool_name and self.tools.get(step.tool_name):
                # Execute the tool
                result = self.tools.execute(step.tool_name, **step.tool_args)
                if result.success:
                    plan.mark_step_completed(step.step_number, result.message)
                    results.append(f"✓ Step {step.step_number}: {result.message}")
                else:
                    plan.mark_step_failed(step.step_number, result.message)
                    results.append(f"✗ Step {step.step_number}: {result.message}")
            else:
                # Reasoning step or unknown tool, mark as completed
                plan.mark_step_completed(step.step_number, "Completed")
                results.append(f"✓ Step {step.step_number}: {step.description}")

            self.plans.save(plan)

        plan.complete()
        self.plans.save(plan)
        self._log_plan(plan)

        final_text = f"Plan completed: {plan.title}\n\n" + "\n".join(results)
        return AgentResponse(text=final_text)

    # ─────────────────────────────────────────────────────────────────────────

    async def transcribe_audio(self, audio_path: Path) -> str | None:
        """Transcribe audio file using OpenAI Whisper."""
        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return response.text
        except Exception as e:
            logger.error(f"{Colors.RED}Transcription failed: {e}{Colors.RESET}")
            return None

    def _format_args(self, args: dict) -> str:
        """Format tool arguments for logging."""
        parts = []
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 50:
                v = v[:50] + "..."
            parts.append(f"{k}={repr(v)}")
        return ", ".join(parts)

    def _format_output(self, data: any, max_lines: int = 10, max_chars: int = 500) -> str:
        """Format tool output data for logging."""
        if data is None:
            return ""

        if isinstance(data, str):
            lines = data.split("\n")
            if len(lines) > max_lines:
                output = "\n".join(lines[:max_lines])
                output += f"\n... ({len(lines) - max_lines} more lines)"
            else:
                output = data
            if len(output) > max_chars:
                output = output[:max_chars] + f"... ({len(data)} chars total)"
            return output

        if isinstance(data, list):
            if len(data) == 0:
                return "[]"
            if len(data) <= 5:
                items = [self._format_output_item(item) for item in data]
                return "[\n    " + ",\n    ".join(items) + "\n  ]"
            else:
                items = [self._format_output_item(item) for item in data[:5]]
                return "[\n    " + ",\n    ".join(items) + f"\n    ... ({len(data) - 5} more)\n  ]"

        if isinstance(data, dict):
            return self._format_output_item(data)

        return str(data)[:max_chars]

    def _format_output_item(self, item: any, max_len: int = 80) -> str:
        """Format a single item in output."""
        if isinstance(item, str):
            if len(item) > max_len:
                return repr(item[:max_len] + "...")
            return repr(item)
        if isinstance(item, dict):
            parts = []
            for k, v in item.items():
                v_str = repr(v) if not isinstance(v, (list, dict)) else f"({type(v).__name__})"
                if len(v_str) > 40:
                    v_str = v_str[:40] + "..."
                parts.append(f"{k}={v_str}")
            return "{" + ", ".join(parts) + "}"
        return repr(item)

    def _execute_tool_call(
        self, tool_call, user_id: int, pending_list: list[PendingConfirmation]
    ) -> str:
        """Execute a single tool call and return result as string.

        If the tool requires confirmation and confirmations are enabled,
        creates a pending confirmation and adds it to pending_list.
        """
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            logger.error(f"  {Colors.RED}✗ {name}: Invalid arguments{Colors.RESET}")
            return json.dumps({"error": f"Invalid arguments for {name}"})

        # Log tool call
        args_str = self._format_args(args)
        logger.info(f"  {Colors.CYAN}→ {name}({Colors.RESET}{args_str}{Colors.CYAN}){Colors.RESET}")

        # Check if tool requires confirmation
        tool = self.tools.get(name)
        settings = self.user_settings.get()

        if tool and tool.requires_confirmation and settings.require_confirmations:
            # For update_note, capture the original content to show before/after
            confirmation_args = args.copy()
            if name == "update_note":
                try:
                    path = args.get("path", "")
                    if path:
                        full_path = self.settings.vault_path / path
                        if not full_path.suffix:
                            full_path = full_path.with_suffix(".md")
                        if full_path.exists():
                            confirmation_args["_original_content"] = full_path.read_text(
                                encoding="utf-8"
                            )
                except Exception:
                    pass  # If we can't read, just skip the before preview

            # Create pending confirmation
            message = tool.get_confirmation_message(**args)
            confirmation = self.pending_confirmations.create(
                user_id=user_id,
                tool_name=name,
                tool_args=confirmation_args,
                message=message,
            )
            pending_list.append(confirmation)
            logger.info(f"    {Colors.YELLOW}⏳ Awaiting confirmation: {message}{Colors.RESET}")
            return json.dumps(
                {
                    "success": True,
                    "awaiting_confirmation": True,
                    "confirmation_id": confirmation.confirmation_id,
                    "message": f"Action requires confirmation: {message}",
                },
                default=str,
            )

        # Execute the tool directly
        result = self.tools.execute(name, **args)

        # Log result
        if result.success:
            logger.info(f"    {Colors.GREEN}✓ {result.message}{Colors.RESET}")
        else:
            logger.warning(f"    {Colors.RED}✗ {result.message}{Colors.RESET}")

        # Log output data
        if result.data is not None:
            formatted_output = self._format_output(result.data)
            if formatted_output:
                for line in formatted_output.split("\n"):
                    logger.info(f"    {Colors.DIM}{line}{Colors.RESET}")

        return json.dumps(
            {
                "success": result.success,
                "message": result.message,
                "data": result.data,
            },
            default=str,
        )

    async def process_message(
        self,
        user_id: int,
        message: str,
        progress_callback: Callable[[ProgressUpdate], None] | None = None,
    ) -> AgentResponse:
        """Process a user message and return the agent's response.

        Args:
            user_id: The user's ID
            message: The user's message
            progress_callback: Optional callback for live progress updates
        """
        # Set current user for task tracking
        self._current_user_id = user_id

        logger.info("")
        logger.info(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")
        logger.info(f"{Colors.BOLD}{Colors.BLUE}User:{Colors.RESET} {message}")

        # Cleanup expired confirmations and old plans
        settings = self.user_settings.get()
        self.pending_confirmations.cleanup_expired(settings.confirmation_timeout_minutes)
        self.plans.cleanup_old()

        # Check for plan request
        if self._is_plan_request(message):
            plan = await self._create_plan(user_id, message)
            if plan:
                self.history.add(user_id, {"role": "user", "content": message})
                plan_summary = f"I've created a plan: **{plan.title}**\n\n{plan.to_telegram_text()}"
                self.history.add(user_id, {"role": "assistant", "content": plan_summary})
                return AgentResponse(text=plan_summary, pending_plan=plan)
            # If plan parsing failed, fall through to normal processing

        # Add user message to history
        self.history.add(user_id, {"role": "user", "content": message})

        # Build messages for API
        messages = self._build_messages(user_id)

        tool_calls_made = 0
        pending_confirmations: list[PendingConfirmation] = []

        while tool_calls_made < MAX_TOOL_CALLS:
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools.get_openai_tools(),
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message

            # Log assistant thinking/reasoning
            if assistant_message.content:
                if assistant_message.tool_calls:
                    # Reasoning before tool calls
                    logger.info(f"{Colors.DIM}💭 {assistant_message.content}{Colors.RESET}")
                    # Send progress update with reasoning
                    if progress_callback:
                        progress_callback(
                            ProgressUpdate(
                                reasoning=assistant_message.content,
                                tasks=self._get_current_tasks(user_id),
                            )
                        )
                else:
                    # Final response
                    logger.info(
                        f"{Colors.BOLD}{Colors.MAGENTA}Knap:{Colors.RESET} {assistant_message.content}"
                    )

            # Add assistant message to conversation
            messages.append(assistant_message.model_dump())

            # Check if we need to execute tools
            if not assistant_message.tool_calls:
                # No more tool calls, we have the final response
                final_response = assistant_message.content or ""

                # Add to persistent history
                self.history.add(user_id, {"role": "assistant", "content": final_response})

                # Send final progress update
                if progress_callback:
                    progress_callback(ProgressUpdate(is_final=True))

                return AgentResponse(
                    text=final_response, pending_confirmations=pending_confirmations
                )

            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                tool_calls_made += 1

                # Parse args for progress display
                try:
                    args = json.loads(tool_call.function.arguments)
                    args_str = self._format_args(args)
                except json.JSONDecodeError:
                    args_str = tool_call.function.arguments

                # Send progress update before tool execution
                if progress_callback:
                    progress_callback(
                        ProgressUpdate(
                            tool_name=tool_call.function.name,
                            tool_args=args_str,
                            tasks=self._get_current_tasks(user_id),
                        )
                    )

                result = self._execute_tool_call(tool_call, user_id, pending_confirmations)

                # Send progress update after tool execution
                if progress_callback:
                    # Truncate result for display
                    result_preview = result[:200] + "..." if len(result) > 200 else result
                    progress_callback(
                        ProgressUpdate(
                            tool_name=tool_call.function.name,
                            tool_result=result_preview,
                            tasks=self._get_current_tasks(user_id),
                        )
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

                if tool_calls_made >= MAX_TOOL_CALLS:
                    logger.warning(
                        f"{Colors.YELLOW}Max tool calls ({MAX_TOOL_CALLS}) reached, generating final response{Colors.RESET}"
                    )
                    break

        # If we hit the limit, get a final response without tools
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        final_response = response.choices[0].message.content or ""
        logger.info(f"{Colors.BOLD}{Colors.MAGENTA}Knap:{Colors.RESET} {final_response}")
        self.history.add(user_id, {"role": "assistant", "content": final_response})

        # Send final progress update
        if progress_callback:
            progress_callback(ProgressUpdate(is_final=True))

        return AgentResponse(text=final_response, pending_confirmations=pending_confirmations)

    def _get_current_tasks(self, user_id: int) -> list[dict] | None:
        """Get current task list for progress updates."""
        task_list = self.task_lists.get(user_id)
        if not task_list or not task_list.tasks:
            return None
        return [t.to_dict() for t in task_list.tasks]

    def execute_confirmed(self, confirmation_id: str) -> str | None:
        """Execute a confirmed tool call. Returns result message or None if not found."""
        confirmation = self.pending_confirmations.remove(confirmation_id)
        if not confirmation:
            return None

        logger.info(f"  {Colors.GREEN}✓ Confirmed:{Colors.RESET} {confirmation.message}")

        # Filter out internal keys (prefixed with _) that were added for display purposes
        tool_args = {k: v for k, v in confirmation.tool_args.items() if not k.startswith("_")}

        result = self.tools.execute(confirmation.tool_name, **tool_args)

        if result.success:
            logger.info(f"    {Colors.GREEN}✓ {result.message}{Colors.RESET}")
        else:
            logger.warning(f"    {Colors.RED}✗ {result.message}{Colors.RESET}")

        return result.message

    def reject_confirmation(self, confirmation_id: str) -> str | None:
        """Reject a pending confirmation. Returns message or None if not found."""
        confirmation = self.pending_confirmations.remove(confirmation_id)
        if not confirmation:
            return None

        logger.info(f"  {Colors.RED}✗ Rejected:{Colors.RESET} {confirmation.message}")

        return f"Cancelled: {confirmation.message}"
