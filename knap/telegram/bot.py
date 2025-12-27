"""Telegram bot setup and initialization."""

import html
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from knap.agent import AgentResponse, ProgressUpdate
from knap.agent.core import Colors
from knap.agent.planning import Plan
from knap.config import Settings
from knap.processors import get_processor
from knap.processors.image_processor import ImageProcessor
from knap.storage import PendingConfirmation

if TYPE_CHECKING:
    from knap.agent.core import Agent

logger = logging.getLogger(__name__)


def _format_confirmation_html(confirmation: PendingConfirmation) -> str:
    """Format a confirmation message with HTML for Telegram."""
    tool = confirmation.tool_name
    args = confirmation.tool_args

    try:
        if tool == "edit_note":
            path = html.escape(str(args.get("path", "")))
            old_text = str(args.get("old_text", ""))
            new_text = str(args.get("new_text", ""))
            old = html.escape(old_text[:50] + ("..." if len(old_text) > 50 else ""))
            new = html.escape(new_text[:50] + ("..." if len(new_text) > 50 else ""))
            return f"✏️ <b>Edit</b> <code>{path}</code>\n<pre>{old}</pre>\n↓\n<pre>{new}</pre>"
        elif tool == "create_note":
            path = html.escape(str(args.get("path", "")))
            content = str(args.get("content", ""))
            preview = html.escape(content[:100] + ("..." if len(content) > 100 else ""))
            return f"📝 <b>Create</b> <code>{path}</code>\n<pre>{preview}</pre>"
        elif tool == "update_note":
            path = html.escape(str(args.get("path", "")))
            new_content = str(args.get("content", ""))
            new_preview = html.escape(new_content[:80] + ("..." if len(new_content) > 80 else ""))

            # Check if we have original content for before/after
            original = args.get("_original_content")
            if original:
                old_preview = html.escape(
                    str(original)[:80] + ("..." if len(str(original)) > 80 else "")
                )
                return (
                    f"📄 <b>Replace</b> <code>{path}</code>\n"
                    f"<pre>{old_preview}</pre>\n"
                    f"↓\n"
                    f"<pre>{new_preview}</pre>"
                )
            else:
                return f"📄 <b>Replace</b> <code>{path}</code>\n<pre>{new_preview}</pre>"
        elif tool == "append_to_note":
            path = html.escape(str(args.get("path", "")))
            content = str(args.get("content", ""))
            preview = html.escape(content[:100] + ("..." if len(content) > 100 else ""))
            return f"➕ <b>Append to</b> <code>{path}</code>\n<pre>{preview}</pre>"
        elif tool == "delete_note":
            path = html.escape(str(args.get("path", "")))
            return f"🗑️ <b>Delete</b> <code>{path}</code>"
        elif tool == "set_frontmatter":
            path = html.escape(str(args.get("path", "")))
            frontmatter = args.get("frontmatter", {})
            fields = ", ".join(str(k) for k in frontmatter.keys()) if frontmatter else ""
            return f"⚙️ <b>Set frontmatter</b> <code>{path}</code>: {html.escape(fields)}"
        else:
            return f"⏳ {html.escape(str(confirmation.message))}"
    except Exception as e:
        logger.exception(f"Error formatting confirmation HTML: {e}")
        return f"⏳ {html.escape(str(confirmation.message))}"


def _format_plan_html(plan: Plan, max_length: int = 3500) -> str:
    """Format a plan for Telegram display using HTML."""
    lines = [f"📋 <b>{html.escape(plan.title)}</b>", ""]

    if plan.description:
        lines.append(html.escape(plan.description[:200]))
        lines.append("")

    lines.append("<b>Steps:</b>")
    for step in plan.steps:
        if step.status.value == "completed":
            icon = "✅"
        elif step.status.value == "in_progress":
            icon = "⏳"
        elif step.status.value == "failed":
            icon = "❌"
        else:
            icon = "⬜"

        step_text = html.escape(step.description[:80])
        tool_info = f" <code>{step.tool_name}</code>" if step.tool_name else ""
        lines.append(f"{icon} {step.step_number}. {step_text}{tool_info}")

    text = "\n".join(lines)

    # Truncate if too long
    if len(text) > max_length:
        text = text[: max_length - 20] + "\n\n<i>... (truncated)</i>"

    return text


def _format_progress_html(update: ProgressUpdate) -> str:
    """Format a progress update for Telegram display using HTML."""
    lines = []

    # Show current reasoning
    if update.reasoning:
        reasoning_text = html.escape(update.reasoning[:300])
        if len(update.reasoning) > 300:
            reasoning_text += "..."
        lines.append(f"💭 <i>{reasoning_text}</i>")
        lines.append("")

    # Show tool execution
    if update.tool_name:
        if update.tool_result:
            # Tool completed
            lines.append(f"✓ <code>{update.tool_name}</code>")
        else:
            # Tool starting
            lines.append(f"⏳ <code>{update.tool_name}</code>")
            if update.tool_args:
                args_text = html.escape(update.tool_args[:100])
                if len(update.tool_args) > 100:
                    args_text += "..."
                lines.append(f"   <i>{args_text}</i>")

    # Show task list
    if update.tasks:
        lines.append("")
        lines.append("<b>Tasks:</b>")
        for task in update.tasks:
            status = task.get("status", "pending")
            if status == "completed":
                icon = "✅"
            elif status == "in_progress":
                icon = "⏳"
            else:
                icon = "⬜"

            # Use active_form for in_progress, content otherwise
            if status == "in_progress":
                text = task.get("active_form", task.get("content", ""))
            else:
                text = task.get("content", "")

            lines.append(f"{icon} {html.escape(text[:50])}")

    return "\n".join(lines) if lines else "⏳ Processing..."


async def _post_init(application) -> None:
    """Called after bot is initialized."""
    bot_info = await application.bot.get_me()
    logger.info(f"{Colors.GREEN}Connected as @{bot_info.username}{Colors.RESET}")


class TelegramBot:
    """Telegram bot wrapper with authentication."""

    def __init__(self, settings: Settings, agent: "Agent") -> None:
        self.settings = settings
        self.agent = agent
        self.app = (
            Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()
        )
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Register message handlers."""
        # Commands
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("clear", self._handle_clear))

        # Regular messages
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # Voice messages
        self.app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

        # Document messages (PDF, CSV, etc.)
        self.app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))

        # Photo messages
        self.app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))

        # Callback queries for confirmation buttons
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is in the allowed list."""
        return user_id in self.settings.allowed_users

    async def _handle_start(self, update: Update, context) -> None:
        """Handle /start command."""
        if not update.effective_user or not update.message:
            return

        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized. Access denied.")
            return

        await update.message.reply_text(
            "Welcome to Knap! I'm your Obsidian assistant.\n\n"
            "Send me a message to interact with your vault.\n"
            "Use /help for available commands."
        )

    async def _handle_help(self, update: Update, context) -> None:
        """Handle /help command."""
        if not update.effective_user or not update.message:
            return

        if not self._is_authorized(update.effective_user.id):
            return

        await update.message.reply_text(
            "*Available Commands*\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/clear - Clear conversation history\n\n"
            "*What I can do*\n"
            "- Read and search your notes\n"
            "- Create and update notes\n"
            "- Navigate your vault structure\n"
            "- Work with daily notes\n"
            "- Manage tags and frontmatter\n\n"
            "You can also send voice messages!",
            parse_mode="Markdown",
        )

    async def _handle_clear(self, update: Update, context) -> None:
        """Handle /clear command - reset conversation history."""
        if not update.effective_user or not update.message:
            return

        if not self._is_authorized(update.effective_user.id):
            return

        user_id = update.effective_user.id
        self.agent.clear_history(user_id)
        await update.message.reply_text("Conversation history cleared.")

    async def _handle_message(self, update: Update, context) -> None:
        """Handle regular text messages."""
        if not update.effective_user or not update.message or not update.message.text:
            return

        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("Unauthorized. Access denied.")
            return

        # Send initial progress message
        progress_message = await update.message.reply_text(
            "⏳ Processing...",
            parse_mode="HTML",
        )

        # Track last update content to avoid unnecessary edits
        last_content = "⏳ Processing..."

        async def update_progress(progress: ProgressUpdate) -> None:
            """Update the progress message with new content."""
            nonlocal last_content

            if progress.is_final:
                return  # Will be replaced with final response

            try:
                new_content = _format_progress_html(progress)
                # Only update if content changed (avoid rate limits)
                if new_content != last_content:
                    await progress_message.edit_text(new_content, parse_mode="HTML")
                    last_content = new_content
            except Exception as e:
                logger.debug(f"Failed to update progress message: {e}")

        def progress_callback(progress: ProgressUpdate) -> None:
            """Sync callback that schedules async update."""
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(update_progress(progress))
            except RuntimeError:
                pass  # No running loop, skip update

        try:
            response = await self.agent.process_message(
                user_id, update.message.text, progress_callback
            )

            # Delete progress message and send final response
            try:
                await progress_message.delete()
            except Exception:
                pass  # Ignore if can't delete

            await self._send_response(update, response)
        except Exception as e:
            logger.exception("Error processing message")
            try:
                await progress_message.edit_text(f"❌ Error: {e}")
            except Exception:
                await update.message.reply_text(f"Error: {e}")

    async def _handle_voice(self, update: Update, context) -> None:
        """Handle voice messages - transcribe and process."""
        if not update.effective_user or not update.message or not update.message.voice:
            return

        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("Unauthorized. Access denied.")
            return

        # Show typing indicator while processing
        await update.message.chat.send_action("typing")

        try:
            # Download voice file
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Transcribe with Whisper
                transcription = await self.agent.transcribe_audio(tmp_path)

                if not transcription:
                    await update.message.reply_text("Could not transcribe audio.")
                    return

                # Process transcribed text
                response = await self.agent.process_message(user_id, transcription)
                await self._send_response(update, response)

            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.exception("Error processing voice message")
            await update.message.reply_text(f"Error: {e}")

    async def _handle_document(self, update: Update, context) -> None:
        """Handle document messages (PDF, CSV, etc.)."""
        if not update.effective_user or not update.message or not update.message.document:
            return

        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("Unauthorized. Access denied.")
            return

        document = update.message.document
        filename = document.file_name or "document"
        mime_type = document.mime_type or ""

        # Get appropriate processor
        processor = get_processor(mime_type, filename)
        if not processor:
            await update.message.reply_text(
                f"Unsupported file type: {mime_type or filename}\n"
                "Supported: CSV, PDF, images (PNG, JPG, GIF, WebP)"
            )
            return

        # Send processing indicator
        progress_message = await update.message.reply_text(
            f"⏳ Processing {filename}...",
            parse_mode="HTML",
        )

        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            suffix = Path(filename).suffix or ".tmp"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Process the file
                result = processor.process(tmp_path, filename)

                if not result.success:
                    await progress_message.edit_text(f"❌ Error: {result.error}")
                    return

                # Get caption as user instruction (if any)
                caption = update.message.caption or ""
                user_message = (
                    f"{caption}\n\n[Attached file: {filename}]\n{result.text}"
                    if caption
                    else f"[Attached file: {filename}]\n{result.text}"
                )

                # Delete progress message
                await progress_message.delete()

                # Process with agent
                await self._handle_message_with_content(update, context, user_id, user_message)

            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.exception("Error processing document")
            try:
                await progress_message.edit_text(f"❌ Error: {e}")
            except Exception:
                await update.message.reply_text(f"Error: {e}")

    async def _handle_photo(self, update: Update, context) -> None:
        """Handle photo messages using Vision API."""
        if not update.effective_user or not update.message or not update.message.photo:
            return

        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("Unauthorized. Access denied.")
            return

        # Get the largest photo
        photo = update.message.photo[-1]

        # Send processing indicator
        progress_message = await update.message.reply_text(
            "⏳ Analyzing image...",
            parse_mode="HTML",
        )

        try:
            # Download photo
            file = await context.bot.get_file(photo.file_id)

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Process with Vision API
                processor = ImageProcessor(self.agent.client)

                # Use caption as custom prompt if provided
                caption = update.message.caption or ""
                prompt = (
                    caption
                    if caption
                    else "Describe this image in detail. If there's text, transcribe it."
                )

                result = processor.process(tmp_path, "photo.jpg", prompt=prompt)

                if not result.success:
                    await progress_message.edit_text(f"❌ Error: {result.error}")
                    return

                # Build message for agent
                user_message = f"[Image analysis]\n{result.text}"
                if caption:
                    user_message = f"{caption}\n\n{user_message}"

                # Delete progress message
                await progress_message.delete()

                # Process with agent
                await self._handle_message_with_content(update, context, user_id, user_message)

            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.exception("Error processing photo")
            try:
                await progress_message.edit_text(f"❌ Error: {e}")
            except Exception:
                await update.message.reply_text(f"Error: {e}")

    async def _handle_message_with_content(
        self, update: Update, context, user_id: int, content: str
    ) -> None:
        """Process a message with pre-extracted content."""
        # Send progress message
        progress_message = await update.message.reply_text(
            "⏳ Processing...",
            parse_mode="HTML",
        )

        last_content = "⏳ Processing..."

        async def update_progress(progress: ProgressUpdate) -> None:
            nonlocal last_content
            if progress.is_final:
                return
            try:
                new_content = _format_progress_html(progress)
                if new_content != last_content:
                    await progress_message.edit_text(new_content, parse_mode="HTML")
                    last_content = new_content
            except Exception as e:
                logger.debug(f"Failed to update progress: {e}")

        def progress_callback(progress: ProgressUpdate) -> None:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(update_progress(progress))
            except RuntimeError:
                pass

        try:
            response = await self.agent.process_message(user_id, content, progress_callback)

            try:
                await progress_message.delete()
            except Exception:
                pass

            await self._send_response(update, response)
        except Exception as e:
            logger.exception("Error processing message")
            try:
                await progress_message.edit_text(f"❌ Error: {e}")
            except Exception:
                await update.message.reply_text(f"Error: {e}")

    async def _handle_callback(self, update: Update, context) -> None:
        """Handle callback queries from confirmation buttons."""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        user_id = query.from_user.id if query.from_user else None
        if not user_id or not self._is_authorized(user_id):
            await query.edit_message_text("Unauthorized.")
            return

        # Parse callback data: "confirm:ID", "reject:ID", "confirm_all:ID,ID,ID", "reject_all:ID,ID,ID"
        parts = query.data.split(":", 1)
        if len(parts) != 2:
            return

        action, data = parts

        if action == "confirm":
            result = self.agent.execute_confirmed(data)
            if result:
                await query.edit_message_text(f"✓ {result}")
            else:
                await query.edit_message_text("Action expired or already processed.")
        elif action == "reject":
            result = self.agent.reject_confirmation(data)
            if result:
                await query.edit_message_text(f"✗ {result}")
            else:
                await query.edit_message_text("Action expired or already processed.")
        elif action == "confirm_all":
            ids = data.split(",")
            results = []
            for cid in ids:
                result = self.agent.execute_confirmed(cid)
                if result:
                    results.append(f"✓ {result}")
            if results:
                await query.edit_message_text("\n".join(results))
            else:
                await query.edit_message_text("All actions expired or already processed.")
        elif action == "reject_all":
            ids = data.split(",")
            count = 0
            for cid in ids:
                if self.agent.reject_confirmation(cid):
                    count += 1
            await query.edit_message_text(f"✗ Cancelled {count} action(s)")
        elif action == "execute_plan":
            plan = self.agent.approve_plan(data)
            if plan:
                await query.edit_message_text(
                    f"▶️ Executing plan: <b>{html.escape(plan.title)}</b>...",
                    parse_mode="HTML",
                )
                # Execute the plan
                try:
                    response = await self.agent.execute_plan(plan)
                    # Send execution results
                    if query.message:
                        await query.message.reply_text(response.text)
                except Exception as e:
                    logger.exception("Error executing plan")
                    if query.message:
                        await query.message.reply_text(f"Error executing plan: {e}")
            else:
                await query.edit_message_text("Plan expired or already processed.")
        elif action == "cancel_plan":
            plan = self.agent.reject_plan(data)
            if plan:
                await query.edit_message_text(
                    f"✗ Plan cancelled: {html.escape(plan.title)}", parse_mode="HTML"
                )
            else:
                await query.edit_message_text("Plan expired or already processed.")

    async def _send_response(self, update: Update, response: AgentResponse) -> None:
        """Send response with optional confirmation buttons or plan approval."""
        if not update.message:
            return

        # Handle pending plan (skip main text as plan already has structured display)
        if response.pending_plan:
            plan = response.pending_plan
            keyboard = [
                [
                    InlineKeyboardButton(
                        "▶️ Execute Plan", callback_data=f"execute_plan:{plan.plan_id}"
                    ),
                    InlineKeyboardButton("✗ Cancel", callback_data=f"cancel_plan:{plan.plan_id}"),
                ]
            ]
            await update.message.reply_text(
                _format_plan_html(plan),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            return

        # Send main text response
        await self._send_text(update, response.text)

        # Send confirmation buttons for each pending action
        confirmations = response.pending_confirmations
        if confirmations:
            logger.info(f"Sending {len(confirmations)} confirmation button(s)")

        # If multiple confirmations, show "Confirm All" option first
        if len(confirmations) > 1:
            all_ids = ",".join(c.confirmation_id for c in confirmations)
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"✓ Confirm All ({len(confirmations)})",
                        callback_data=f"confirm_all:{all_ids}",
                    ),
                    InlineKeyboardButton("✗ Cancel All", callback_data=f"reject_all:{all_ids}"),
                ]
            ]
            await update.message.reply_text(
                f"📋 <b>{len(confirmations)} actions pending</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )

        for confirmation in confirmations:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✓ Confirm", callback_data=f"confirm:{confirmation.confirmation_id}"
                    ),
                    InlineKeyboardButton(
                        "✗ Cancel", callback_data=f"reject:{confirmation.confirmation_id}"
                    ),
                ]
            ]
            try:
                await update.message.reply_text(
                    _format_confirmation_html(confirmation),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.exception(f"Failed to send confirmation button: {e}")
                # Fallback to plain text
                await update.message.reply_text(
                    f"⏳ {confirmation.message}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )

    async def _send_text(self, update: Update, text: str) -> None:
        """Send text, chunking if necessary (Telegram limit: 4096 chars)."""
        if not update.message or not text:
            return

        max_length = 4096

        # Check if text looks like it contains markdown note content (checkboxes, etc.)
        # In that case, wrap in <pre> for monospace display
        has_note_content = "- [" in text or "- [ ]" in text or "- [x]" in text

        if has_note_content:
            # Wrap in HTML pre tag for clean display of markdown content
            escaped = html.escape(text)
            formatted = f"<pre>{escaped}</pre>"
            parse_mode = "HTML"
        else:
            formatted = text
            parse_mode = None  # Plain text, no parsing

        if len(formatted) <= max_length:
            await update.message.reply_text(formatted, parse_mode=parse_mode)
            return

        # Split into chunks (for plain text)
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_length:
                chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line

        if current:
            chunks.append(current)

        for chunk in chunks:
            if has_note_content:
                escaped = html.escape(chunk)
                await update.message.reply_text(f"<pre>{escaped}</pre>", parse_mode="HTML")
            else:
                await update.message.reply_text(chunk)

    def run(self) -> None:
        """Start the bot (blocking)."""
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
