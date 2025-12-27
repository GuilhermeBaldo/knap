"""Base file processor class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessedContent:
    """Result of processing a file."""

    text: str  # Extracted/described text content
    summary: str  # Brief summary for display
    file_type: str  # Type of file processed
    success: bool = True
    error: str | None = None


class FileProcessor(ABC):
    """Base class for file processors."""

    file_type: str = "unknown"

    @abstractmethod
    def process(self, file_path: Path, filename: str = "") -> ProcessedContent:
        """Process a file and extract its content.

        Args:
            file_path: Path to the file to process
            filename: Original filename (for context)

        Returns:
            ProcessedContent with extracted text and metadata
        """
        pass

    def _error_result(self, error: str) -> ProcessedContent:
        """Create an error result."""
        return ProcessedContent(
            text="",
            summary=f"Error: {error}",
            file_type=self.file_type,
            success=False,
            error=error,
        )
