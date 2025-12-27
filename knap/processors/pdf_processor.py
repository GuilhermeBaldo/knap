"""PDF file processor."""

import logging
from pathlib import Path

from .base import FileProcessor, ProcessedContent

logger = logging.getLogger(__name__)


class PDFProcessor(FileProcessor):
    """Processor for PDF files using PyMuPDF."""

    file_type = "pdf"

    def process(
        self,
        file_path: Path,
        filename: str = "",
        max_pages: int = 20,
        max_chars: int = 50000,
    ) -> ProcessedContent:
        """Process a PDF file and extract its text content.

        Args:
            file_path: Path to the PDF file
            filename: Original filename
            max_pages: Maximum pages to process
            max_chars: Maximum characters to extract

        Returns:
            ProcessedContent with extracted text
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return self._error_result("PyMuPDF not installed. Run: pip install pymupdf")

        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)

            text_parts = []
            chars_extracted = 0
            pages_processed = 0

            for page_num in range(min(total_pages, max_pages)):
                page = doc[page_num]
                page_text = page.get_text()

                if chars_extracted + len(page_text) > max_chars:
                    # Truncate to fit within limit
                    remaining = max_chars - chars_extracted
                    if remaining > 0:
                        text_parts.append(f"--- Page {page_num + 1} ---")
                        text_parts.append(page_text[:remaining])
                        text_parts.append("... (truncated)")
                    break

                text_parts.append(f"--- Page {page_num + 1} ---")
                text_parts.append(page_text)
                chars_extracted += len(page_text)
                pages_processed += 1

            doc.close()

            full_text = "\n\n".join(text_parts)

            # Build summary
            summary_parts = [
                f"PDF: {filename}" if filename else "PDF file",
                f"{total_pages} pages",
            ]

            if pages_processed < total_pages:
                summary_parts.append(f"(processed {pages_processed})")

            # Preview: first ~500 chars
            preview = full_text[:500]
            if len(full_text) > 500:
                preview += "..."

            summary = f"{' | '.join(summary_parts)}\n\n{preview}"

            # Full content
            header = f"## PDF: {filename}" if filename else "## PDF Document"
            text = f"{header}\nPages: {total_pages}\n\n{full_text}"

            return ProcessedContent(
                text=text,
                summary=summary,
                file_type=self.file_type,
            )

        except Exception as e:
            logger.exception(f"Error processing PDF: {e}")
            return self._error_result(str(e))
