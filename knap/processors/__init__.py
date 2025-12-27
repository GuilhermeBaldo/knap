"""File processors for ingesting various file types."""

from .base import FileProcessor, ProcessedContent
from .csv_processor import CSVProcessor
from .image_processor import ImageProcessor
from .pdf_processor import PDFProcessor

__all__ = [
    "FileProcessor",
    "ProcessedContent",
    "CSVProcessor",
    "ImageProcessor",
    "PDFProcessor",
]


def get_processor(mime_type: str, filename: str) -> FileProcessor | None:
    """Get appropriate processor for a file based on MIME type or filename."""
    mime_lower = mime_type.lower() if mime_type else ""
    name_lower = filename.lower() if filename else ""

    # CSV
    if "csv" in mime_lower or name_lower.endswith(".csv"):
        return CSVProcessor()

    # PDF
    if "pdf" in mime_lower or name_lower.endswith(".pdf"):
        return PDFProcessor()

    # Images
    if any(t in mime_lower for t in ["image/", "png", "jpeg", "jpg", "gif", "webp"]):
        return ImageProcessor()
    if any(name_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
        return ImageProcessor()

    return None
