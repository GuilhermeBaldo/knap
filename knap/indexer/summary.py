"""Generate text summary of vault index for system prompt."""

from datetime import datetime, timedelta

from .scanner import NoteInfo, VaultIndex


def generate_vault_summary(index: VaultIndex, max_notes: int = 30) -> str:
    """Generate a concise text summary of the vault for the system prompt.

    Prioritizes:
    1. Recently modified notes (last 7 days)
    2. Most linked-to notes (hub notes)
    3. Alphabetical fallback
    """
    lines = ["## Your Vault\n"]

    # Basic stats
    lines.append(f"**{index.total_notes} notes** indexed\n")

    # Folder structure
    lines.append("**Structure:**")
    for folder in index.folders[:15]:  # Limit folders shown
        indent = "  " * folder.path.count("/")
        folder_name = folder.path.split("/")[-1] if folder.path != "/" else "Root"
        lines.append(f"{indent}- {folder_name}/ ({folder.note_count} notes)")

    if len(index.folders) > 15:
        lines.append(f"  ... and {len(index.folders) - 15} more folders")

    lines.append("")

    # Top tags
    if index.tags:
        sorted_tags = sorted(index.tags.items(), key=lambda x: -x[1])[:15]
        tag_str = ", ".join(f"#{tag} ({count})" for tag, count in sorted_tags)
        lines.append(f"**Top Tags:** {tag_str}\n")

    # Select notes to show
    selected_notes = _select_priority_notes(index.notes, max_notes)

    if selected_notes:
        lines.append("**Key Notes:**")
        for note in selected_notes:
            # Prefer AI summary over basic description
            if note.summary:
                summary_line = f"- **{note.path}** ({note.title}): {note.summary}"
                if note.concepts:
                    summary_line += f" [Topics: {', '.join(note.concepts[:5])}]"
                lines.append(summary_line)
            else:
                desc = f' - "{note.description}"' if note.description else ""
                lines.append(f"- {note.path}: {note.title}{desc}")

        if len(index.notes) > max_notes:
            lines.append(f"\n*... and {len(index.notes) - max_notes} more notes*")

    # Add concept cloud if available
    all_concepts = _collect_concepts(index.notes)
    if all_concepts:
        top_concepts = sorted(all_concepts.items(), key=lambda x: -x[1])[:20]
        concept_str = ", ".join(f"{c} ({n})" for c, n in top_concepts)
        lines.append(f"\n**Key Concepts:** {concept_str}")

    return "\n".join(lines)


def _collect_concepts(notes: list[NoteInfo]) -> dict[str, int]:
    """Collect and count all concepts across notes."""
    concepts: dict[str, int] = {}
    for note in notes:
        for concept in note.concepts:
            concepts[concept] = concepts.get(concept, 0) + 1
    return concepts


def _select_priority_notes(notes: list[NoteInfo], max_count: int) -> list[NoteInfo]:
    """Select the most important notes to show.

    Priority:
    1. Recently modified (last 7 days)
    2. Most linked-to (hub notes)
    3. Alphabetical
    """
    now = datetime.now().timestamp()
    week_ago = now - timedelta(days=7).total_seconds()

    # Categorize notes
    recent: list[NoteInfo] = []
    hub_notes: list[NoteInfo] = []
    other: list[NoteInfo] = []

    for note in notes:
        if note.mtime >= week_ago:
            recent.append(note)
        elif note.backlink_count >= 3:
            hub_notes.append(note)
        else:
            other.append(note)

    # Sort each category
    recent.sort(key=lambda n: -n.mtime)
    hub_notes.sort(key=lambda n: -n.backlink_count)
    other.sort(key=lambda n: n.title.lower())

    # Combine with limits
    result = []

    # Recent notes first (up to 15)
    result.extend(recent[: min(15, max_count)])

    # Hub notes next (up to 10)
    remaining = max_count - len(result)
    if remaining > 0:
        result.extend(hub_notes[: min(10, remaining)])

    # Fill with other notes
    remaining = max_count - len(result)
    if remaining > 0:
        result.extend(other[:remaining])

    return result


def generate_compact_summary(index: VaultIndex) -> str:
    """Generate a very compact summary for token-constrained contexts."""
    lines = [f"Vault: {index.total_notes} notes"]

    # Top 5 folders
    top_folders = sorted(index.folders, key=lambda f: -f.note_count)[:5]
    folder_strs = [f"{f.path}({f.note_count})" for f in top_folders]
    lines.append(f"Folders: {', '.join(folder_strs)}")

    # Top 10 tags
    if index.tags:
        sorted_tags = sorted(index.tags.items(), key=lambda x: -x[1])[:10]
        tag_strs = [f"#{t}({c})" for t, c in sorted_tags]
        lines.append(f"Tags: {', '.join(tag_strs)}")

    return " | ".join(lines)
