"""Vault scanner - builds index of all notes."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class NoteInfo:
    """Information about a single note."""

    path: str
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    mtime: float = 0.0
    backlink_count: int = 0
    # LLM-enriched fields
    summary: str = ""
    concepts: list[str] = field(default_factory=list)
    summary_mtime: float = 0.0  # mtime when summary was generated

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "links": self.links,
            "mtime": self.mtime,
            "backlink_count": self.backlink_count,
            "summary": self.summary,
            "concepts": self.concepts,
            "summary_mtime": self.summary_mtime,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NoteInfo":
        return cls(
            path=data["path"],
            title=data["title"],
            description=data["description"],
            tags=data.get("tags", []),
            links=data.get("links", []),
            mtime=data.get("mtime", 0.0),
            backlink_count=data.get("backlink_count", 0),
            summary=data.get("summary", ""),
            concepts=data.get("concepts", []),
            summary_mtime=data.get("summary_mtime", 0.0),
        )

    def needs_summary(self) -> bool:
        """Check if this note needs its summary regenerated."""
        return self.mtime > self.summary_mtime or not self.summary


@dataclass
class FolderInfo:
    """Information about a folder."""

    path: str
    note_count: int
    subfolders: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "note_count": self.note_count,
            "subfolders": self.subfolders,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderInfo":
        return cls(**data)


@dataclass
class VaultIndex:
    """Complete index of a vault."""

    vault_path: str
    last_indexed: float
    total_notes: int
    folders: list[FolderInfo] = field(default_factory=list)
    tags: dict[str, int] = field(default_factory=dict)
    notes: list[NoteInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "vault_path": self.vault_path,
            "last_indexed": self.last_indexed,
            "total_notes": self.total_notes,
            "folders": [f.to_dict() for f in self.folders],
            "tags": self.tags,
            "notes": [n.to_dict() for n in self.notes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VaultIndex":
        return cls(
            vault_path=data["vault_path"],
            last_indexed=data["last_indexed"],
            total_notes=data["total_notes"],
            folders=[FolderInfo.from_dict(f) for f in data.get("folders", [])],
            tags=data.get("tags", {}),
            notes=[NoteInfo.from_dict(n) for n in data.get("notes", [])],
        )


class VaultScanner:
    """Scans an Obsidian vault and builds an index."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path

    def scan(self, existing_notes: dict[str, NoteInfo] | None = None) -> VaultIndex:
        """Perform a full scan of the vault.

        Args:
            existing_notes: Optional dict of path -> NoteInfo from previous index.
                           Used to preserve summaries for unchanged notes.
        """
        logger.info(f"Scanning vault: {self.vault_path}")
        existing_notes = existing_notes or {}

        notes: list[NoteInfo] = []
        folders: dict[str, FolderInfo] = {}
        tags: dict[str, int] = {}
        link_targets: dict[str, int] = {}  # note name -> backlink count

        # Scan all markdown files
        for md_file in self.vault_path.rglob("*.md"):
            # Skip hidden folders
            if any(part.startswith(".") for part in md_file.parts):
                continue

            try:
                note_info = self._scan_note(md_file)

                # Preserve summary from existing note if content hasn't changed
                existing = existing_notes.get(note_info.path)
                if existing and existing.mtime == note_info.mtime:
                    note_info.summary = existing.summary
                    note_info.concepts = existing.concepts
                    note_info.summary_mtime = existing.summary_mtime

                notes.append(note_info)

                # Count tags
                for tag in note_info.tags:
                    tags[tag] = tags.get(tag, 0) + 1

                # Count outgoing links for backlink calculation
                for link in note_info.links:
                    link_targets[link] = link_targets.get(link, 0) + 1

                # Track folder
                rel_folder = md_file.parent.relative_to(self.vault_path)
                folder_path = str(rel_folder) if str(rel_folder) != "." else "/"

                if folder_path not in folders:
                    folders[folder_path] = FolderInfo(path=folder_path, note_count=0)
                folders[folder_path].note_count += 1

            except Exception as e:
                logger.warning(f"Failed to scan {md_file}: {e}")
                continue

        # Update backlink counts
        for note in notes:
            note_name = Path(note.path).stem.lower()
            note.backlink_count = link_targets.get(note_name, 0)

        # Build folder hierarchy
        folder_list = self._build_folder_hierarchy(folders)

        index = VaultIndex(
            vault_path=str(self.vault_path),
            last_indexed=datetime.now().timestamp(),
            total_notes=len(notes),
            folders=folder_list,
            tags=tags,
            notes=notes,
        )

        logger.info(f"Indexed {len(notes)} notes, {len(tags)} tags, {len(folder_list)} folders")
        return index

    def _scan_note(self, file_path: Path) -> NoteInfo:
        """Extract information from a single note."""
        content = file_path.read_text(encoding="utf-8")
        rel_path = str(file_path.relative_to(self.vault_path))
        mtime = file_path.stat().st_mtime

        # Parse frontmatter
        frontmatter = self._parse_frontmatter(content)

        # Get title
        title = frontmatter.get("title", "")
        if not title:
            # Try first H1 heading
            h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            else:
                title = file_path.stem

        # Get description
        description = frontmatter.get("description", "")
        if not description:
            # Use first non-empty, non-heading line
            description = self._extract_description(content)

        # Get tags from frontmatter and inline
        tags = self._extract_tags(content, frontmatter)

        # Get wikilinks
        links = self._extract_links(content)

        return NoteInfo(
            path=rel_path,
            title=title,
            description=description[:100],  # Limit length
            tags=tags,
            links=links,
            mtime=mtime,
        )

    def _parse_frontmatter(self, content: str) -> dict:
        """Parse YAML frontmatter from note content."""
        if not content.startswith("---"):
            return {}

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}

        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _extract_description(self, content: str) -> str:
        """Extract a brief description from note content."""
        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)

        # Find first paragraph-like content
        for line in content.split("\n"):
            line = line.strip()
            # Skip headings, empty lines, lists, code blocks
            if (
                line
                and not line.startswith("#")
                and not line.startswith("-")
                and not line.startswith("*")
                and not line.startswith("`")
                and not line.startswith(">")
            ):
                # Clean up markdown
                line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # Links
                line = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", line)  # Wikilinks
                line = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", line)  # Bold/italic
                return line[:100]

        return ""

    def _extract_tags(self, content: str, frontmatter: dict) -> list[str]:
        """Extract tags from frontmatter and inline."""
        tags = set()

        # Frontmatter tags
        fm_tags = frontmatter.get("tags", [])
        if isinstance(fm_tags, list):
            tags.update(fm_tags)
        elif isinstance(fm_tags, str):
            tags.add(fm_tags)

        # Inline tags (#tag)
        inline_tags = re.findall(r"(?<!\S)#([a-zA-Z][a-zA-Z0-9_-]*)", content)
        tags.update(inline_tags)

        return list(tags)

    def _extract_links(self, content: str) -> list[str]:
        """Extract wikilinks from content."""
        # Match [[note]] or [[note|alias]] or [[folder/note]]
        matches = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)

        # Normalize: take just the note name (last part of path)
        links = []
        for match in matches:
            note_name = Path(match).stem.lower()
            if note_name not in links:
                links.append(note_name)

        return links

    def _build_folder_hierarchy(self, folders: dict[str, FolderInfo]) -> list[FolderInfo]:
        """Build folder list with subfolder relationships."""
        # Sort by path depth
        sorted_folders = sorted(folders.values(), key=lambda f: f.path.count("/"))

        # Add subfolders
        for folder in sorted_folders:
            if folder.path == "/":
                continue

            parent_path = str(Path(folder.path).parent)
            if parent_path == ".":
                parent_path = "/"

            if parent_path in folders:
                folders[parent_path].subfolders.append(folder.path)

        return sorted_folders
