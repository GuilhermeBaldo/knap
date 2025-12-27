"""Tests for storage modules."""

from pathlib import Path

from knap.storage.history import ConversationHistory
from knap.storage.settings import (
    PendingConfirmationStorage,
    SettingsStorage,
    UserSettings,
)
from knap.storage.vault_index import VaultIndexStorage


class TestConversationHistory:
    """Tests for ConversationHistory."""

    def test_add_and_get_messages(self, tmp_vault: Path):
        history = ConversationHistory(tmp_vault)
        user_id = 12345

        history.add(user_id, {"role": "user", "content": "Hello"})
        history.add(user_id, {"role": "assistant", "content": "Hi there!"})

        messages = history.get(user_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_persistence(self, tmp_vault: Path):
        user_id = 12345

        # Add message
        history1 = ConversationHistory(tmp_vault)
        history1.add(user_id, {"role": "user", "content": "Hello"})

        # Create new instance - should load from disk
        history2 = ConversationHistory(tmp_vault)
        messages = history2.get(user_id)

        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"

    def test_clear_history(self, tmp_vault: Path):
        history = ConversationHistory(tmp_vault)
        user_id = 12345

        history.add(user_id, {"role": "user", "content": "Hello"})
        assert len(history.get(user_id)) == 1

        history.clear(user_id)
        assert len(history.get(user_id)) == 0

    def test_max_messages_limit(self, tmp_vault: Path):
        history = ConversationHistory(tmp_vault, max_messages=5)
        user_id = 12345

        # Add more messages than limit
        for i in range(10):
            history.add(user_id, {"role": "user", "content": f"Message {i}"})

        messages = history.get(user_id)
        assert len(messages) == 5
        # Should keep the most recent messages
        assert messages[0]["content"] == "Message 5"
        assert messages[-1]["content"] == "Message 9"

    def test_separate_users(self, tmp_vault: Path):
        history = ConversationHistory(tmp_vault)

        history.add(111, {"role": "user", "content": "User 1 message"})
        history.add(222, {"role": "user", "content": "User 2 message"})

        assert len(history.get(111)) == 1
        assert len(history.get(222)) == 1
        assert history.get(111)[0]["content"] == "User 1 message"
        assert history.get(222)[0]["content"] == "User 2 message"

    def test_storage_location(self, tmp_vault: Path):
        history = ConversationHistory(tmp_vault)
        user_id = 12345

        history.add(user_id, {"role": "user", "content": "Hello"})

        # Check file is stored in .knap/conversations/
        expected_path = tmp_vault / ".knap" / "conversations" / f"{user_id}.json"
        assert expected_path.exists()


class TestVaultIndexStorage:
    """Tests for VaultIndexStorage."""

    def test_build_index(self, tmp_vault: Path):
        storage = VaultIndexStorage(tmp_vault)
        index = storage.get_index()

        assert index.total_notes >= 3  # Note1, Note2, Inbox/Task
        assert len(index.notes) >= 3

    def test_index_persistence(self, tmp_vault: Path):
        # Build index
        storage1 = VaultIndexStorage(tmp_vault)
        storage1.get_index()

        # Check index file exists
        index_file = tmp_vault / ".knap" / "index.json"
        assert index_file.exists()

        # Load from new instance
        storage2 = VaultIndexStorage(tmp_vault)
        index = storage2.get_index()
        assert index.total_notes >= 3

    def test_rebuild_index(self, tmp_vault: Path):
        storage = VaultIndexStorage(tmp_vault)
        storage.get_index()

        # Add a new note
        (tmp_vault / "NewNote.md").write_text("New content")

        # Rebuild
        index = storage.rebuild()
        assert index.total_notes >= 4

    def test_index_contains_tags(self, tmp_vault: Path):
        storage = VaultIndexStorage(tmp_vault)
        index = storage.get_index()

        # Should find tags from notes
        assert len(index.tags) > 0
        assert "tag1" in index.tags or "project" in index.tags

    def test_index_contains_folders(self, tmp_vault: Path):
        storage = VaultIndexStorage(tmp_vault)
        index = storage.get_index()

        folder_paths = [f.path for f in index.folders]
        assert "Inbox" in folder_paths or any("Inbox" in p for p in folder_paths)

    def test_note_info(self, tmp_vault: Path):
        storage = VaultIndexStorage(tmp_vault)
        index = storage.get_index()

        # Find Note2 which has frontmatter
        note2 = next((n for n in index.notes if "Note2" in n.path), None)
        assert note2 is not None
        assert note2.title == "Custom Title"  # From frontmatter


class TestSettingsStorage:
    """Tests for SettingsStorage."""

    def test_default_settings(self, tmp_vault: Path):
        """Test that default settings are created."""
        storage = SettingsStorage(tmp_vault)
        settings = storage.get()

        assert isinstance(settings, UserSettings)
        assert settings.require_confirmations is True
        assert settings.confirmation_timeout_minutes == 5

    def test_update_settings(self, tmp_vault: Path):
        """Test updating settings."""
        storage = SettingsStorage(tmp_vault)

        # Update confirmation setting
        updated = storage.update(require_confirmations=False)

        assert updated.require_confirmations is False
        assert updated.confirmation_timeout_minutes == 5  # Unchanged

    def test_settings_persistence(self, tmp_vault: Path):
        """Test settings are persisted to disk."""
        storage1 = SettingsStorage(tmp_vault)
        storage1.update(require_confirmations=False, confirmation_timeout_minutes=10)

        # New instance should load from disk
        storage2 = SettingsStorage(tmp_vault)
        settings = storage2.get()

        assert settings.require_confirmations is False
        assert settings.confirmation_timeout_minutes == 10

    def test_settings_file_location(self, tmp_vault: Path):
        """Test settings file is stored in correct location."""
        storage = SettingsStorage(tmp_vault)
        storage.get()

        expected_path = tmp_vault / ".knap" / "settings.json"
        assert expected_path.exists()


class TestPendingConfirmationStorage:
    """Tests for PendingConfirmationStorage."""

    def test_create_confirmation(self, tmp_vault: Path):
        """Test creating a pending confirmation."""
        storage = PendingConfirmationStorage(tmp_vault)

        confirmation = storage.create(
            user_id=12345,
            tool_name="create_note",
            tool_args={"path": "test.md", "content": "Hello"},
            message="Create note 'test.md'?",
        )

        assert confirmation.user_id == 12345
        assert confirmation.tool_name == "create_note"
        assert confirmation.tool_args == {"path": "test.md", "content": "Hello"}
        assert confirmation.message == "Create note 'test.md'?"
        assert len(confirmation.confirmation_id) == 8

    def test_get_confirmation(self, tmp_vault: Path):
        """Test retrieving a pending confirmation."""
        storage = PendingConfirmationStorage(tmp_vault)

        created = storage.create(
            user_id=12345,
            tool_name="delete_note",
            tool_args={"path": "note.md"},
            message="Delete 'note.md'?",
        )

        retrieved = storage.get(created.confirmation_id)
        assert retrieved is not None
        assert retrieved.confirmation_id == created.confirmation_id
        assert retrieved.tool_name == "delete_note"

    def test_remove_confirmation(self, tmp_vault: Path):
        """Test removing a pending confirmation."""
        storage = PendingConfirmationStorage(tmp_vault)

        created = storage.create(
            user_id=12345,
            tool_name="update_note",
            tool_args={"path": "note.md", "content": "New"},
            message="Update 'note.md'?",
        )

        removed = storage.remove(created.confirmation_id)
        assert removed is not None
        assert removed.confirmation_id == created.confirmation_id

        # Should be gone now
        assert storage.get(created.confirmation_id) is None

    def test_get_for_user(self, tmp_vault: Path):
        """Test getting confirmations for a specific user."""
        storage = PendingConfirmationStorage(tmp_vault)

        # Create confirmations for different users
        storage.create(
            user_id=111,
            tool_name="create_note",
            tool_args={"path": "a.md"},
            message="Create a.md",
        )
        storage.create(
            user_id=222,
            tool_name="create_note",
            tool_args={"path": "b.md"},
            message="Create b.md",
        )
        storage.create(
            user_id=111,
            tool_name="delete_note",
            tool_args={"path": "c.md"},
            message="Delete c.md",
        )

        user_111_confirmations = storage.get_for_user(111)
        assert len(user_111_confirmations) == 2

        user_222_confirmations = storage.get_for_user(222)
        assert len(user_222_confirmations) == 1

    def test_persistence(self, tmp_vault: Path):
        """Test confirmations are persisted to disk."""
        storage1 = PendingConfirmationStorage(tmp_vault)
        created = storage1.create(
            user_id=12345,
            tool_name="edit_note",
            tool_args={"path": "note.md", "old_text": "a", "new_text": "b"},
            message="Edit note",
        )

        # New instance should load from disk
        storage2 = PendingConfirmationStorage(tmp_vault)
        retrieved = storage2.get(created.confirmation_id)

        assert retrieved is not None
        assert retrieved.tool_name == "edit_note"

    def test_remove_nonexistent(self, tmp_vault: Path):
        """Test removing a non-existent confirmation."""
        storage = PendingConfirmationStorage(tmp_vault)

        result = storage.remove("nonexistent")
        assert result is None
