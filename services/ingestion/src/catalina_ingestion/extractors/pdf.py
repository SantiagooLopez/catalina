from pathlib import Path
from statistics import median
from typing import Any

import pymupdf

from catalina_ingestion.domain.exceptions import ExtractionError
from catalina_ingestion.domain.extracted import (
    ExtractedBlock,
    ExtractedDocument,
)
from catalina_ingestion.extractors.base import BaseExtractor


class PdfExtractor(BaseExtractor):
    supported_extensions = frozenset({".pdf"})

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            document = pymupdf.open(path)
        except Exception as error:
            raise ExtractionError(
                "PDF_OPEN_ERROR",
                "No fue posible abrir el archivo PDF.",
            ) from error

        try:
            if document.needs_pass:
                raise ExtractionError(
                    "ENCRYPTED_PDF",
                    "El PDF requiere una contraseña.",
                )

            if document.page_count < 1:
                raise ExtractionError(
                    "EMPTY_PDF",
                    "El PDF no contiene páginas.",
                )

            page_structures: list[dict[str, Any]] = []
            font_sizes: list[float] = []

            for page in document:
                page_structure = page.get_text("dict", sort=True)
                page_structures.append(page_structure)

                for raw_block in page_structure.get("blocks", []):
                    if raw_block.get("type") != 0:
                        continue

                    for line in raw_block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()

                            if text:
                                font_sizes.append(float(span.get("size", 0)))

            body_font_size = median(font_sizes) if font_sizes else 0
            blocks: list[ExtractedBlock] = []
            current_section: str | None = None
            text_character_count = 0

            for page_index, page_structure in enumerate(
                page_structures,
                start=1,
            ):
                for raw_block in page_structure.get("blocks", []):
                    block_data = self._parse_text_block(raw_block)

                    if block_data is None:
                        continue

                    text = block_data["text"]
                    maximum_font_size = block_data["maximum_font_size"]
                    is_bold = block_data["is_bold"]

                    is_heading = self._is_heading(
                        text=text,
                        maximum_font_size=maximum_font_size,
                        body_font_size=body_font_size,
                        is_bold=is_bold,
                    )

                    block_type = "heading" if is_heading else "paragraph"

                    if is_heading:
                        current_section = text

                    text_character_count += len(text)

                    blocks.append(
                        ExtractedBlock(
                            index=len(blocks),
                            text=text,
                            block_type=block_type,
                            page_number=page_index,
                            section=current_section,
                            metadata={
                                "bbox": [
                                    round(float(value), 2)
                                    for value in raw_block.get(
                                        "bbox",
                                        [],
                                    )
                                ],
                                "maximum_font_size": maximum_font_size,
                                "bold": is_bold,
                            },
                        )
                    )

            minimum_characters = max(20, document.page_count * 10)

            if text_character_count < minimum_characters:
                raise ExtractionError(
                    "PDF_REQUIERE_OCR",
                    "El PDF contiene muy poco texto extraíble y probablemente está escaneado.",
                    {
                        "page_count": document.page_count,
                        "extracted_characters": text_character_count,
                    },
                )

            metadata = {key: value for key, value in (document.metadata or {}).items() if value}

            title = metadata.get("title")

            if not title:
                title = next(
                    (block.text for block in blocks if block.block_type == "heading"),
                    None,
                )

            return ExtractedDocument(
                title=title,
                page_count=document.page_count,
                blocks=blocks,
                metadata={
                    "format": "pdf",
                    "body_font_size": body_font_size,
                    "pdf_metadata": metadata,
                },
            )

        except ExtractionError:
            raise
        except Exception as error:
            raise ExtractionError(
                "PDF_EXTRACTION_ERROR",
                "Ocurrió un error durante la extracción del PDF.",
            ) from error
        finally:
            document.close()

    def _parse_text_block(
        self,
        raw_block: dict[str, Any],
    ) -> dict[str, Any] | None:
        if raw_block.get("type") != 0:
            return None

        lines: list[str] = []
        font_sizes: list[float] = []
        bold = False

        for line in raw_block.get("lines", []):
            line_parts: list[str] = []

            for span in line.get("spans", []):
                span_text = span.get("text", "").strip()

                if not span_text:
                    continue

                line_parts.append(span_text)
                font_sizes.append(float(span.get("size", 0)))

                flags = int(span.get("flags", 0))
                bold = bold or bool(flags & 16)

            if line_parts:
                lines.append(" ".join(line_parts))

        text = " ".join(lines).strip()

        if not text:
            return None

        return {
            "text": text,
            "maximum_font_size": max(font_sizes, default=0),
            "is_bold": bold,
        }

    def _is_heading(
        self,
        text: str,
        maximum_font_size: float,
        body_font_size: float,
        is_bold: bool,
    ) -> bool:
        if len(text) > 180 or len(text.split()) > 20:
            return False

        if body_font_size <= 0:
            return False

        considerably_larger = maximum_font_size >= body_font_size * 1.25
        slightly_larger_bold = is_bold and maximum_font_size >= body_font_size * 1.05

        return considerably_larger or slightly_larger_bold
