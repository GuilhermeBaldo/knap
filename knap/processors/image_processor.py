"""Image file processor using OpenAI Vision API."""

import base64
import logging
from pathlib import Path

from openai import OpenAI

from .base import FileProcessor, ProcessedContent

logger = logging.getLogger(__name__)


class ImageProcessor(FileProcessor):
    """Processor for images using OpenAI Vision API."""

    file_type = "image"

    def __init__(self, openai_client: OpenAI | None = None):
        """Initialize with optional OpenAI client."""
        self._client = openai_client

    def set_client(self, client: OpenAI) -> None:
        """Set the OpenAI client."""
        self._client = client

    def process(
        self,
        file_path: Path,
        filename: str = "",
        prompt: str = "Describe this image in detail. If there's text, transcribe it.",
    ) -> ProcessedContent:
        """Process an image using OpenAI Vision API.

        Args:
            file_path: Path to the image file
            filename: Original filename
            prompt: Prompt for the vision model

        Returns:
            ProcessedContent with image description/transcription
        """
        if not self._client:
            return self._error_result("OpenAI client not configured")

        try:
            # Read and encode image
            image_data = file_path.read_bytes()
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Determine media type
            suffix = file_path.suffix.lower()
            media_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_types.get(suffix, "image/jpeg")

            # Call Vision API
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}",
                                    "detail": "auto",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
            )

            description = response.choices[0].message.content or ""

            # Build summary (first ~300 chars)
            summary_text = description[:300]
            if len(description) > 300:
                summary_text += "..."

            summary = f"Image: {filename}\n\n{summary_text}" if filename else summary_text

            # Full content
            header = f"## Image: {filename}" if filename else "## Image Analysis"
            text = f"{header}\n\n{description}"

            return ProcessedContent(
                text=text,
                summary=summary,
                file_type=self.file_type,
            )

        except Exception as e:
            logger.exception(f"Error processing image: {e}")
            return self._error_result(str(e))
