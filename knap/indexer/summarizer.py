"""LLM-powered note summarization for vault indexing."""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)

# Model to use for summarization (fast and cheap)
SUMMARIZER_MODEL = "gpt-4o-mini"

# Maximum content length to send for summarization (chars)
MAX_CONTENT_LENGTH = 8000

SUMMARIZE_PROMPT = """\
Analyze this note and provide:
1. A concise 1-2 sentence summary of what this note is about
2. A list of 3-7 key concepts/topics covered

Respond in JSON format:
{"summary": "...", "concepts": ["concept1", "concept2", ...]}

Note content:
"""


@dataclass
class NoteSummary:
    """Result of summarizing a note."""

    summary: str
    concepts: list[str]


class NoteSummarizer:
    """Generates AI summaries for notes using OpenAI."""

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def summarize(self, content: str, title: str = "") -> NoteSummary | None:
        """Generate summary and concepts for a note.

        Args:
            content: The note content (markdown)
            title: Optional title for context

        Returns:
            NoteSummary with summary and concepts, or None if failed
        """
        # Skip very short notes
        if len(content.strip()) < 50:
            return NoteSummary(
                summary=content.strip()[:100] if content.strip() else "Empty note",
                concepts=[],
            )

        # Truncate very long content
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "\n\n[content truncated...]"

        # Add title context if available
        prompt_content = content
        if title:
            prompt_content = f"Title: {title}\n\n{content}"

        try:
            response = self.client.chat.completions.create(
                model=SUMMARIZER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes notes concisely. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": SUMMARIZE_PROMPT + prompt_content},
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content or "{}"
            result = json.loads(result_text)

            return NoteSummary(
                summary=result.get("summary", ""),
                concepts=result.get("concepts", []),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse summary JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to summarize note: {e}")
            return None

    def summarize_batch(
        self, notes: list[tuple[str, str, str]], on_progress: callable = None
    ) -> dict[str, NoteSummary]:
        """Summarize multiple notes.

        Args:
            notes: List of (path, title, content) tuples
            on_progress: Optional callback(current, total) for progress updates

        Returns:
            Dict mapping path to NoteSummary
        """
        results = {}
        total = len(notes)

        for i, (path, title, content) in enumerate(notes):
            if on_progress:
                on_progress(i + 1, total)

            summary = self.summarize(content, title)
            if summary:
                results[path] = summary

        return results
