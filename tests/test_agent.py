"""Tests for agent core."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from knap.agent.core import KNAP_NOTE_NAME, Agent
from knap.config import Settings


@pytest.fixture
def mock_settings(tmp_vault: Path, monkeypatch):
    """Create mock settings for testing."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
    monkeypatch.setenv("ALLOWED_USER_IDS", "12345")
    return Settings()


class TestAgent:
    """Tests for Agent class."""

    def test_init(self, mock_settings):
        """Test agent initialization."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            assert agent.settings == mock_settings
            assert agent.model == mock_settings.openai_model
            assert agent.tools is not None

    def test_clear_history(self, mock_settings):
        """Test clearing conversation history."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Add some history
            agent.history.add(12345, {"role": "user", "content": "Hello"})
            assert len(agent.history.get(12345)) == 1

            # Clear history
            agent.clear_history(12345)
            assert len(agent.history.get(12345)) == 0

    def test_get_user_guidelines_no_file(self, mock_settings):
        """Test reading user guidelines when file doesn't exist."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            guidelines = agent._get_user_guidelines()
            assert guidelines is None

    def test_get_user_guidelines_with_file(self, mock_settings, tmp_vault: Path):
        """Test reading user guidelines from KNAP.md."""
        # Create KNAP.md
        shard_note = tmp_vault / KNAP_NOTE_NAME
        shard_note.write_text("# Custom Guidelines\n\nMy custom rules here.")

        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            guidelines = agent._get_user_guidelines()
            assert guidelines is not None
            assert "Custom Guidelines" in guidelines
            assert "custom rules" in guidelines

    def test_get_user_guidelines_strips_frontmatter(self, mock_settings, tmp_vault: Path):
        """Test that frontmatter is stripped from KNAP.md."""
        shard_note = tmp_vault / KNAP_NOTE_NAME
        shard_note.write_text("---\ntitle: Shard Config\n---\n\nActual content here.")

        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            guidelines = agent._get_user_guidelines()
            assert guidelines is not None
            assert "---" not in guidelines
            assert "Actual content here" in guidelines

    def test_build_messages_includes_system_prompt(self, mock_settings):
        """Test that messages include system prompt."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            messages = agent._build_messages(12345)

            assert len(messages) >= 1
            assert messages[0]["role"] == "system"
            assert "Knap" in messages[0]["content"]

    def test_build_messages_includes_history(self, mock_settings):
        """Test that messages include conversation history."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Add some history
            agent.history.add(12345, {"role": "user", "content": "Hello"})
            agent.history.add(12345, {"role": "assistant", "content": "Hi!"})

            messages = agent._build_messages(12345)

            # Should have system + 2 history messages
            assert len(messages) >= 3
            assert messages[1]["role"] == "user"
            assert messages[2]["role"] == "assistant"

    def test_build_messages_includes_vault_summary(self, mock_settings):
        """Test that messages include vault summary."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            messages = agent._build_messages(12345)

            # System prompt should include vault info
            assert "Vault" in messages[0]["content"] or "notes" in messages[0]["content"].lower()

    def test_build_messages_includes_user_guidelines(self, mock_settings, tmp_vault: Path):
        """Test that user guidelines are included in system prompt."""
        shard_note = tmp_vault / KNAP_NOTE_NAME
        shard_note.write_text("Always respond in Portuguese.")

        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            messages = agent._build_messages(12345)

            assert "Portuguese" in messages[0]["content"]
            assert "User Guidelines" in messages[0]["content"]

    def test_refresh_index(self, mock_settings):
        """Test vault index refresh."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Should not raise
            agent.refresh_index()

    def test_format_args(self, mock_settings):
        """Test argument formatting for logging."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Short args
            result = agent._format_args({"path": "note.md", "content": "hello"})
            assert "path='note.md'" in result
            assert "content='hello'" in result

            # Long args get truncated
            long_content = "x" * 100
            result = agent._format_args({"content": long_content})
            assert "..." in result
            assert len(result) < 100

    def test_execute_tool_call_success(self, mock_settings, tmp_vault: Path):
        """Test successful tool execution."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Create a mock tool call
            tool_call = Mock()
            tool_call.function.name = "read_note"
            tool_call.function.arguments = '{"path": "Note1.md"}'

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert result_data["success"] is True

    def test_execute_tool_call_invalid_json(self, mock_settings):
        """Test tool execution with invalid JSON arguments."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            tool_call = Mock()
            tool_call.function.name = "read_note"
            tool_call.function.arguments = "invalid json"

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert "error" in result_data

    def test_execute_tool_call_unknown_tool(self, mock_settings):
        """Test execution of unknown tool."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            tool_call = Mock()
            tool_call.function.name = "unknown_tool"
            tool_call.function.arguments = "{}"

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert result_data["success"] is False


class TestAgentProcessMessage:
    """Tests for agent message processing."""

    @pytest.mark.asyncio
    async def test_process_message_simple(self, mock_settings):
        """Test processing a simple message without tool calls."""
        with patch("knap.agent.core.OpenAI") as mock_openai:
            # Setup mock response
            mock_response = Mock()
            mock_message = Mock()
            mock_message.content = "Hello! How can I help?"
            mock_message.tool_calls = None
            mock_message.model_dump.return_value = {
                "role": "assistant",
                "content": "Hello! How can I help?",
            }
            mock_response.choices = [Mock(message=mock_message)]

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = Agent(mock_settings)
            response = await agent.process_message(12345, "Hello")

            assert response.text == "Hello! How can I help?"
            assert response.pending_confirmations == []

    @pytest.mark.asyncio
    async def test_process_message_with_tool_call(self, mock_settings, tmp_vault: Path):
        """Test processing a message that triggers tool calls."""
        with patch("knap.agent.core.OpenAI") as mock_openai:
            # First response: tool call
            tool_call = Mock()
            tool_call.id = "call_123"
            tool_call.function.name = "read_note"
            tool_call.function.arguments = '{"path": "Note1.md"}'

            mock_message1 = Mock()
            mock_message1.content = None
            mock_message1.tool_calls = [tool_call]
            mock_message1.model_dump.return_value = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call_123", "function": {"name": "read_note"}}],
            }

            # Second response: final answer
            mock_message2 = Mock()
            mock_message2.content = "I read the note for you."
            mock_message2.tool_calls = None
            mock_message2.model_dump.return_value = {
                "role": "assistant",
                "content": "I read the note for you.",
            }

            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = [
                Mock(choices=[Mock(message=mock_message1)]),
                Mock(choices=[Mock(message=mock_message2)]),
            ]
            mock_openai.return_value = mock_client

            agent = Agent(mock_settings)
            response = await agent.process_message(12345, "Read Note1")

            assert response.text == "I read the note for you."
            assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_process_message_saves_history(self, mock_settings):
        """Test that messages are saved to history."""
        with patch("knap.agent.core.OpenAI") as mock_openai:
            mock_response = Mock()
            mock_message = Mock()
            mock_message.content = "Response"
            mock_message.tool_calls = None
            mock_message.model_dump.return_value = {"role": "assistant", "content": "Response"}
            mock_response.choices = [Mock(message=mock_message)]

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = Agent(mock_settings)
            await agent.process_message(12345, "Hello")

            history = agent.history.get(12345)
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "Hello"
            assert history[1]["role"] == "assistant"


class TestAgentConfirmation:
    """Tests for agent confirmation handling."""

    def test_execute_confirmed(self, mock_settings, tmp_vault: Path):
        """Test executing a confirmed tool call."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Create a pending confirmation for create_note
            confirmation = agent.pending_confirmations.create(
                user_id=12345,
                tool_name="create_note",
                tool_args={"path": "NewNote.md", "content": "Hello World"},
                message="Create note 'NewNote.md'?",
            )

            # Execute the confirmation
            result = agent.execute_confirmed(confirmation.confirmation_id)

            assert result is not None
            assert "Created" in result or "NewNote" in result

            # Note should be created
            assert (tmp_vault / "NewNote.md").exists()

    def test_execute_confirmed_not_found(self, mock_settings):
        """Test executing a non-existent confirmation."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            result = agent.execute_confirmed("nonexistent")
            assert result is None

    def test_reject_confirmation(self, mock_settings, tmp_vault: Path):
        """Test rejecting a pending confirmation."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Create a pending confirmation
            confirmation = agent.pending_confirmations.create(
                user_id=12345,
                tool_name="delete_note",
                tool_args={"path": "Note1.md"},
                message="Delete 'Note1.md'?",
            )

            # Reject the confirmation
            result = agent.reject_confirmation(confirmation.confirmation_id)

            assert result is not None
            assert "Cancelled" in result

            # Note should NOT be deleted
            assert (tmp_vault / "Note1.md").exists()

            # Confirmation should be removed
            assert agent.pending_confirmations.get(confirmation.confirmation_id) is None

    def test_tool_call_requires_confirmation(self, mock_settings, tmp_vault: Path):
        """Test that write tools require confirmation when enabled."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Ensure confirmations are enabled
            agent.user_settings.update(require_confirmations=True)

            # Create a mock tool call for a write operation
            tool_call = Mock()
            tool_call.function.name = "create_note"
            tool_call.function.arguments = '{"path": "TestNote.md", "content": "Test"}'

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert result_data.get("awaiting_confirmation") is True
            assert len(pending_list) == 1

            # Note should NOT be created yet
            assert not (tmp_vault / "TestNote.md").exists()

    def test_tool_call_no_confirmation_when_disabled(self, mock_settings, tmp_vault: Path):
        """Test that write tools execute directly when confirmations disabled."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Disable confirmations
            agent.user_settings.update(require_confirmations=False)

            # Create a mock tool call for a write operation
            tool_call = Mock()
            tool_call.function.name = "create_note"
            tool_call.function.arguments = '{"path": "DirectNote.md", "content": "Test"}'

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data.get("awaiting_confirmation") is None
            assert len(pending_list) == 0

            # Note should be created directly
            assert (tmp_vault / "DirectNote.md").exists()

    def test_read_tool_no_confirmation(self, mock_settings, tmp_vault: Path):
        """Test that read tools don't require confirmation."""
        with patch("knap.agent.core.OpenAI"):
            agent = Agent(mock_settings)

            # Ensure confirmations are enabled
            agent.user_settings.update(require_confirmations=True)

            # Create a mock tool call for a read operation
            tool_call = Mock()
            tool_call.function.name = "read_note"
            tool_call.function.arguments = '{"path": "Note1.md"}'

            pending_list = []
            result = agent._execute_tool_call(tool_call, user_id=12345, pending_list=pending_list)

            import json

            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data.get("awaiting_confirmation") is None
            assert len(pending_list) == 0


class TestAgentTranscription:
    """Tests for audio transcription."""

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, mock_settings, tmp_path: Path):
        """Test successful audio transcription."""
        # Create a dummy audio file
        audio_file = tmp_path / "test.ogg"
        audio_file.write_bytes(b"fake audio data")

        with patch("knap.agent.core.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.audio.transcriptions.create.return_value = Mock(text="Transcribed text")
            mock_openai.return_value = mock_client

            agent = Agent(mock_settings)
            result = await agent.transcribe_audio(audio_file)

            assert result == "Transcribed text"

    @pytest.mark.asyncio
    async def test_transcribe_audio_failure(self, mock_settings, tmp_path: Path):
        """Test audio transcription failure."""
        audio_file = tmp_path / "test.ogg"
        audio_file.write_bytes(b"fake audio data")

        with patch("knap.agent.core.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.audio.transcriptions.create.side_effect = Exception("API error")
            mock_openai.return_value = mock_client

            agent = Agent(mock_settings)
            result = await agent.transcribe_audio(audio_file)

            assert result is None
