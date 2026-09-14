import re
from pathlib import Path

from charset_normalizer import from_bytes

from catalina_ingestion.domain.exceptions import ExtractionError
from catalina_ingestion.domain.extracted import (
    ExtractedBlock,
    ExtractedDocument,
)
from catalina_ingestion.extractors.base import BaseExtractor


class TextExtractor(BaseExtractor):
    supported_extensions = frozenset({".txt"})

    def extract(self, path: Path) -> ExtractedDocument:
        raw_content = path.read_bytes()
        decoding_result = from_bytes(raw_content).best()

        if decoding_result is None:
            raise ExtractionError(
                "TEXT_DECODING_ERROR",
                "No fue posible identificar la codificación del texto.",
            )

        content = str(decoding_result).replace("\r\n", "\n")
        content = content.replace("\r", "\n")

        if not content.strip():
            raise ExtractionError(
                "EMPTY_TEXT_DOCUMENT",
                "El archivo de texto está vacío.",
            )

        logical_pages = content.split("\f")
        blocks: list[ExtractedBlock] = []
        current_section: str | None = None
        title: str | None = None

        for page_number, page in enumerate(
            logical_pages,
            start=1,
        ):
            paragraphs = re.split(
                r"\n\s*\n",
                page,
            )

            for paragraph in paragraphs:
                segments = self._split_embedded_headings(paragraph)

                for text in segments:
                    is_heading = self._is_heading(text)

                    is_list = self._is_list(text)

                    if is_heading:
                        text = text.lstrip("#").strip()

                        current_section = text
                        title = title or text
                        block_type = "heading"

                    elif is_list:
                        block_type = "list"

                    else:
                        block_type = "paragraph"

                    blocks.append(
                        ExtractedBlock(
                            index=len(blocks),
                            text=text,
                            block_type=block_type,
                            page_number=page_number,
                            section=current_section,
                        )
                    )

        if not blocks:
            raise ExtractionError(
                "EMPTY_TEXT_DOCUMENT",
                "El archivo no contiene bloques de texto.",
            )

        return ExtractedDocument(
            title=title or path.stem,
            page_count=len(logical_pages),
            blocks=blocks,
            metadata={
                "format": "txt",
                "encoding": (decoding_result.encoding),
            },
        )

    def _split_embedded_headings(
        self,
        paragraph: str,
    ) -> list[str]:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]

        if not lines:
            return []

        segments: list[str] = []
        buffer: list[str] = []

        for line in lines:
            if self._is_heading(line):
                if buffer:
                    segments.append("\n".join(buffer).strip())
                    buffer = []

                segments.append(line)
                continue

            buffer.append(line)

        if buffer:
            segments.append("\n".join(buffer).strip())

        return segments

    def _is_heading(
        self,
        text: str,
    ) -> bool:
        if "\n" in text or len(text) > 150:
            return False

        stripped = text.strip()

        return (
            stripped.startswith("#")
            or (stripped.isupper() and any(character.isalpha() for character in stripped))
            or (stripped.endswith(":") and len(stripped.split()) <= 12)
        )

    def _is_list(
        self,
        text: str,
    ) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not lines:
            return False

        list_pattern = re.compile(r"^([-*•]|\d+[.)])\s+")

        return all(list_pattern.match(line) for line in lines)
