"""Persistent storage for vault index."""

import json
import logging
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from knap.indexer.scanner import NoteInfo, VaultIndex, VaultScanner
from knap.indexer.summarizer import NoteSummarizer

logger = logging.getLogger(__name__)


class VaultIndexStorage:
    """Manages persistent vault index with auto-refresh."""

    def __init__(self, vault_path: Path, openai_client: OpenAI | None = None) -> None:
        self.vault_path = vault_path
        self.knap_dir = vault_path / ".knap"
        self.index_file = self.knap_dir / "index.json"
        self.scanner = VaultScanner(vault_path)
        self._index: VaultIndex | None = None
        self._openai_client = openai_client
        self._summarizer: NoteSummarizer | None = None

    def set_openai_client(self, client: OpenAI) -> None:
        """Set OpenAI client for summarization."""
        self._openai_client = client
        self._summarizer = NoteSummarizer(client)

    @property
    def summarizer(self) -> NoteSummarizer | None:
        """Get summarizer, lazily creating if client is available."""
        if self._summarizer is None and self._openai_client is not None:
            self._summarizer = NoteSummarizer(self._openai_client)
        return self._summarizer

    def get_index(self) -> VaultIndex:
        """Get the current index, loading or building as needed."""
        if self._index is None:
            self._index = self._load_or_build()

        # Check if refresh needed
        if self._needs_refresh():
            logger.info("Vault changed, refreshing index...")
            self._index = self._rebuild()

        return self._index

    def rebuild(self) -> VaultIndex:
        """Force a full rebuild of the index."""
        self._index = self._rebuild()
        return self._index

    def _needs_refresh(self) -> bool:
        """Check if vault has changed since last index."""
        if self._index is None:
            return True

        try:
            # Check vault folder mtime
            vault_mtime = self._get_vault_mtime()
            return vault_mtime > self._index.last_indexed
        except Exception:
            return True

    def _get_vault_mtime(self) -> float:
        """Get the most recent modification time in the vault."""
        latest_mtime = 0.0

        # Check a sample of files for performance
        count = 0
        for md_file in self.vault_path.rglob("*.md"):
            if any(part.startswith(".") for part in md_file.parts):
                continue

            try:
                mtime = md_file.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except Exception:
                continue

            count += 1
            # For large vaults, sample first 100 files + check vault dir mtime
            if count >= 100:
                break

        # Also check vault directory itself
        try:
            vault_dir_mtime = self.vault_path.stat().st_mtime
            if vault_dir_mtime > latest_mtime:
                latest_mtime = vault_dir_mtime
        except Exception:
            pass

        return latest_mtime

    def _load_or_build(self) -> VaultIndex:
        """Load index from disk or build if not available."""
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                index = VaultIndex.from_dict(data)
                logger.info(f"Loaded vault index ({index.total_notes} notes)")
                return index
            except Exception as e:
                logger.warning(f"Failed to load index, rebuilding: {e}")

        return self._rebuild()

    def _rebuild(self) -> VaultIndex:
        """Build a new index and save to disk."""
        # Get existing notes to preserve summaries for unchanged notes
        existing_notes: dict[str, NoteInfo] = {}
        if self._index:
            existing_notes = {n.path: n for n in self._index.notes}

        index = self.scanner.scan(existing_notes)

        # Enrich with summaries if we have a summarizer
        if self.summarizer:
            self._enrich_summaries(index)

        self._save(index)
        return index

    def _enrich_summaries(self, index: VaultIndex) -> None:
        """Generate summaries for notes that need them."""
        notes_needing_summary = [n for n in index.notes if n.needs_summary()]

        if not notes_needing_summary:
            logger.info("All notes have up-to-date summaries")
            return

        logger.info(f"Generating summaries for {len(notes_needing_summary)} notes...")

        # Read content and summarize
        for i, note in enumerate(notes_needing_summary):
            try:
                note_path = self.vault_path / note.path
                content = note_path.read_text(encoding="utf-8")

                summary_result = self.summarizer.summarize(content, note.title)
                if summary_result:
                    note.summary = summary_result.summary
                    note.concepts = summary_result.concepts
                    note.summary_mtime = datetime.now().timestamp()

                    logger.debug(f"  [{i + 1}/{len(notes_needing_summary)}] {note.path}")

            except Exception as e:
                logger.warning(f"Failed to summarize {note.path}: {e}")

        logger.info("Summarization complete")

    def enrich_summaries_async(self, on_progress: callable = None) -> int:
        """Manually trigger summary enrichment for notes missing summaries.

        Args:
            on_progress: Optional callback(current, total, note_path)

        Returns:
            Number of notes summarized
        """
        if not self.summarizer:
            logger.warning("No OpenAI client configured for summarization")
            return 0

        if self._index is None:
            self._index = self._load_or_build()

        notes_needing_summary = [n for n in self._index.notes if n.needs_summary()]

        if not notes_needing_summary:
            return 0

        count = 0
        for i, note in enumerate(notes_needing_summary):
            if on_progress:
                on_progress(i + 1, len(notes_needing_summary), note.path)

            try:
                note_path = self.vault_path / note.path
                content = note_path.read_text(encoding="utf-8")

                summary_result = self.summarizer.summarize(content, note.title)
                if summary_result:
                    note.summary = summary_result.summary
                    note.concepts = summary_result.concepts
                    note.summary_mtime = datetime.now().timestamp()
                    count += 1

            except Exception as e:
                logger.warning(f"Failed to summarize {note.path}: {e}")

        # Save updated index
        self._save(self._index)
        return count

    def _save(self, index: VaultIndex) -> None:
        """Save index to disk (inside vault/.knap/)."""
        try:
            self.knap_dir.mkdir(parents=True, exist_ok=True)
            self.index_file.write_text(
                json.dumps(index.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"Saved vault index to {self.index_file}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
