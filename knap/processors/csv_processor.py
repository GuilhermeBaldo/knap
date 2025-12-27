"""CSV file processor."""

import csv
from pathlib import Path

from .base import FileProcessor, ProcessedContent


class CSVProcessor(FileProcessor):
    """Processor for CSV files."""

    file_type = "csv"

    def process(
        self,
        file_path: Path,
        filename: str = "",
        max_rows: int = 100,
        max_preview_rows: int = 5,
    ) -> ProcessedContent:
        """Process a CSV file and extract its content as formatted text.

        Args:
            file_path: Path to the CSV file
            filename: Original filename
            max_rows: Maximum rows to include in full content
            max_preview_rows: Rows to show in summary

        Returns:
            ProcessedContent with CSV data as markdown table
        """
        try:
            # Try different encodings
            content = None
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                return self._error_result("Could not decode CSV file")

            # Parse CSV
            reader = csv.reader(content.splitlines())
            rows = list(reader)

            if not rows:
                return self._error_result("CSV file is empty")

            headers = rows[0]
            data_rows = rows[1:]

            # Build markdown table for full content
            full_table = self._build_markdown_table(headers, data_rows[:max_rows])

            # Build summary
            total_rows = len(data_rows)
            preview_table = self._build_markdown_table(headers, data_rows[:max_preview_rows])

            summary_parts = [
                f"CSV: {filename or 'file'}" if filename else "CSV file",
                f"{len(headers)} columns, {total_rows} rows",
            ]

            if total_rows > max_preview_rows:
                summary_parts.append(f"(showing first {max_preview_rows})")

            summary = f"{' | '.join(summary_parts)}\n\n{preview_table}"

            # Full text includes all data (up to max)
            text_parts = [
                f"## CSV Data: {filename}" if filename else "## CSV Data",
                f"Columns: {', '.join(headers)}",
                f"Total rows: {total_rows}",
                "",
                full_table,
            ]

            if total_rows > max_rows:
                text_parts.append(f"\n... ({total_rows - max_rows} more rows not shown)")

            return ProcessedContent(
                text="\n".join(text_parts),
                summary=summary,
                file_type=self.file_type,
            )

        except Exception as e:
            return self._error_result(str(e))

    def _build_markdown_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Build a markdown table from headers and rows."""
        if not headers:
            return ""

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Build table
        lines = []

        # Header
        header_cells = [h.ljust(widths[i]) for i, h in enumerate(headers)]
        lines.append("| " + " | ".join(header_cells) + " |")

        # Separator
        separators = ["-" * w for w in widths]
        lines.append("| " + " | ".join(separators) + " |")

        # Data rows
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                width = widths[i] if i < len(widths) else len(str(cell))
                cells.append(str(cell).ljust(width))
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)
