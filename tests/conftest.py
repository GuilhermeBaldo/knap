"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault directory with sample notes."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create some sample notes
    (vault / "Note1.md").write_text("# Note 1\n\nThis is note 1 content.\n\n#tag1 #tag2")
    (vault / "Note2.md").write_text(
        "---\ntitle: Custom Title\ntags: [project]\n---\n\nNote 2 with frontmatter."
    )

    # Create a subfolder
    inbox = vault / "Inbox"
    inbox.mkdir()
    (inbox / "Task.md").write_text("- [ ] Buy groceries\n- [x] Done task")

    # Create daily notes folder
    daily = vault / "Daily Notes"
    daily.mkdir()

    return vault


@pytest.fixture
def sample_note_content() -> str:
    """Sample note content for testing."""
    return """---
title: Test Note
tags: [test, sample]
---

# Test Note

This is a test note with some content.

- [ ] Task 1
- [x] Task 2

#inline-tag
"""
