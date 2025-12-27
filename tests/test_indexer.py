"""Tests for indexer module."""

from pathlib import Path

from knap.indexer.scanner import FolderInfo, NoteInfo, VaultIndex, VaultScanner
from knap.indexer.summary import generate_compact_summary, generate_vault_summary


class TestNoteInfo:
    """Tests for NoteInfo dataclass."""

    def test_to_dict(self):
        note = NoteInfo(
            path="test.md",
            title="Test",
            description="A test note",
            tags=["tag1", "tag2"],
            links=["other"],
            mtime=1234567890.0,
            backlink_count=5,
        )

        data = note.to_dict()
        assert data["path"] == "test.md"
        assert data["title"] == "Test"
        assert data["tags"] == ["tag1", "tag2"]

    def test_from_dict(self):
        data = {
            "path": "test.md",
            "title": "Test",
            "description": "A test note",
            "tags": ["tag1"],
            "links": [],
            "mtime": 1234567890.0,
            "backlink_count": 0,
        }

        note = NoteInfo.from_dict(data)
        assert note.path == "test.md"
        assert note.title == "Test"
        assert note.tags == ["tag1"]

    def test_summary_and_concepts_fields(self):
        note = NoteInfo(
            path="test.md",
            title="Test",
            description="A test note",
            summary="This note discusses testing practices.",
            concepts=["testing", "automation", "quality"],
            summary_mtime=1234567890.0,
        )

        data = note.to_dict()
        assert data["summary"] == "This note discusses testing practices."
        assert data["concepts"] == ["testing", "automation", "quality"]
        assert data["summary_mtime"] == 1234567890.0

        restored = NoteInfo.from_dict(data)
        assert restored.summary == note.summary
        assert restored.concepts == note.concepts
        assert restored.summary_mtime == note.summary_mtime

    def test_needs_summary_when_no_summary(self):
        note = NoteInfo(path="test.md", title="Test", description="", mtime=100.0)
        assert note.needs_summary() is True

    def test_needs_summary_when_outdated(self):
        note = NoteInfo(
            path="test.md",
            title="Test",
            description="",
            mtime=200.0,  # Note was modified
            summary="Old summary",
            summary_mtime=100.0,  # Summary is older
        )
        assert note.needs_summary() is True

    def test_needs_summary_when_up_to_date(self):
        note = NoteInfo(
            path="test.md",
            title="Test",
            description="",
            mtime=100.0,
            summary="Current summary",
            summary_mtime=200.0,  # Summary is newer than mtime
        )
        assert note.needs_summary() is False


class TestFolderInfo:
    """Tests for FolderInfo dataclass."""

    def test_to_dict(self):
        folder = FolderInfo(
            path="Inbox",
            note_count=5,
            subfolders=["Inbox/Archive"],
        )

        data = folder.to_dict()
        assert data["path"] == "Inbox"
        assert data["note_count"] == 5

    def test_from_dict(self):
        data = {
            "path": "Inbox",
            "note_count": 5,
            "subfolders": [],
        }

        folder = FolderInfo.from_dict(data)
        assert folder.path == "Inbox"
        assert folder.note_count == 5


class TestVaultIndex:
    """Tests for VaultIndex dataclass."""

    def test_to_dict_and_from_dict(self):
        index = VaultIndex(
            vault_path="/path/to/vault",
            last_indexed=1234567890.0,
            total_notes=10,
            folders=[FolderInfo(path="/", note_count=10)],
            tags={"tag1": 5, "tag2": 3},
            notes=[NoteInfo(path="test.md", title="Test", description="")],
        )

        data = index.to_dict()
        restored = VaultIndex.from_dict(data)

        assert restored.vault_path == index.vault_path
        assert restored.total_notes == index.total_notes
        assert len(restored.folders) == 1
        assert len(restored.notes) == 1


class TestVaultScanner:
    """Tests for VaultScanner."""

    def test_scan_vault(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        assert index.total_notes >= 3
        assert len(index.notes) >= 3

    def test_scan_extracts_title_from_frontmatter(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        note2 = next((n for n in index.notes if "Note2" in n.path), None)
        assert note2 is not None
        assert note2.title == "Custom Title"

    def test_scan_extracts_title_from_filename(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        # Note1 has H1 heading, should use that
        note1 = next((n for n in index.notes if "Note1" in n.path), None)
        assert note1 is not None
        assert note1.title == "Note 1"

    def test_scan_extracts_tags(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        # Should find inline tags from Note1
        assert "tag1" in index.tags
        assert "tag2" in index.tags

        # Should find frontmatter tags from Note2
        assert "project" in index.tags

    def test_scan_extracts_links(self, tmp_vault: Path):
        # Create a note with wikilinks
        (tmp_vault / "LinkNote.md").write_text("Links to [[Note1]] and [[Note2|alias]]")

        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        link_note = next((n for n in index.notes if "LinkNote" in n.path), None)
        assert link_note is not None
        assert "note1" in link_note.links
        assert "note2" in link_note.links

    def test_scan_counts_backlinks(self, tmp_vault: Path):
        # Create notes that link to Note1
        (tmp_vault / "Linker1.md").write_text("Links to [[Note1]]")
        (tmp_vault / "Linker2.md").write_text("Also links to [[Note1]]")

        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        note1 = next((n for n in index.notes if n.path == "Note1.md"), None)
        assert note1 is not None
        assert note1.backlink_count >= 2

    def test_scan_builds_folder_structure(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        folder_paths = [f.path for f in index.folders]
        assert any("Inbox" in p for p in folder_paths)

    def test_scan_skips_hidden_folders(self, tmp_vault: Path):
        # Create a hidden folder with a note
        hidden = tmp_vault / ".hidden"
        hidden.mkdir()
        (hidden / "secret.md").write_text("Hidden note")

        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        # Should not include notes from hidden folders
        assert not any(".hidden" in n.path for n in index.notes)

    def test_scan_extracts_description(self, tmp_vault: Path):
        # Create a note with content
        (tmp_vault / "DescNote.md").write_text("# Title\n\nThis is the description paragraph.")

        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        note = next((n for n in index.notes if "DescNote" in n.path), None)
        assert note is not None
        assert "description paragraph" in note.description

    def test_scan_preserves_summaries_for_unchanged_notes(self, tmp_vault: Path):
        # First scan
        scanner = VaultScanner(tmp_vault)
        index1 = scanner.scan()

        # Add summaries to notes
        for note in index1.notes:
            note.summary = f"Summary for {note.title}"
            note.concepts = ["concept1", "concept2"]
            note.summary_mtime = note.mtime + 100  # Newer than mtime

        # Second scan with existing notes
        existing = {n.path: n for n in index1.notes}
        index2 = scanner.scan(existing_notes=existing)

        # Summaries should be preserved
        for note in index2.notes:
            if note.path in existing:
                assert note.summary == f"Summary for {note.title}"
                assert note.concepts == ["concept1", "concept2"]


class TestGenerateVaultSummary:
    """Tests for generate_vault_summary."""

    def test_generates_summary(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_vault_summary(index)

        assert "## Your Vault" in summary
        assert "notes" in summary.lower()
        assert "Structure:" in summary

    def test_includes_tags(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_vault_summary(index)

        assert "Top Tags:" in summary or "Tags:" in summary

    def test_includes_key_notes(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_vault_summary(index)

        assert "Key Notes:" in summary

    def test_respects_max_notes(self, tmp_vault: Path):
        # Create many notes
        for i in range(50):
            (tmp_vault / f"Note{i:02d}.md").write_text(f"Content {i}")

        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_vault_summary(index, max_notes=5)

        # Should mention there are more notes
        assert "more notes" in summary.lower()

    def test_includes_ai_summaries_when_available(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        # Add AI summaries to notes
        for note in index.notes:
            note.summary = "This is an AI-generated summary."
            note.concepts = ["productivity", "note-taking"]
            note.summary_mtime = note.mtime + 100

        summary = generate_vault_summary(index)

        # Should include the AI summary
        assert "AI-generated summary" in summary
        # Should include concepts
        assert "productivity" in summary or "Topics:" in summary

    def test_includes_concept_cloud(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        # Add concepts to notes
        for i, note in enumerate(index.notes):
            note.concepts = ["shared_concept", f"unique_{i}"]

        summary = generate_vault_summary(index)

        # Should include key concepts section
        assert "Key Concepts:" in summary
        assert "shared_concept" in summary


class TestGenerateCompactSummary:
    """Tests for generate_compact_summary."""

    def test_generates_compact_summary(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_compact_summary(index)

        assert "Vault:" in summary
        assert "notes" in summary
        assert "|" in summary  # Uses pipe separator

    def test_compact_summary_short(self, tmp_vault: Path):
        scanner = VaultScanner(tmp_vault)
        index = scanner.scan()

        summary = generate_compact_summary(index)

        # Should be reasonably short
        assert len(summary) < 500
