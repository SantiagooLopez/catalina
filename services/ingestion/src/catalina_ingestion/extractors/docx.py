from collections.abc import Iterator
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from catalina_ingestion.domain.exceptions import ExtractionError
from catalina_ingestion.domain.extracted import (
    ExtractedBlock,
    ExtractedDocument,
)
from catalina_ingestion.extractors.base import BaseExtractor


class DocxExtractor(BaseExtractor):
    supported_extensions = frozenset({".docx"})

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            document = Document(path)
        except Exception as error:
            raise ExtractionError(
                "DOCX_OPEN_ERROR",
                "No fue posible abrir el documento Word.",
            ) from error

        blocks: list[ExtractedBlock] = []
        current_section: str | None = None
        first_heading: str | None = None

        try:
            for item in self._iter_document_blocks(document):
                if isinstance(item, Paragraph):
                    text = item.text.strip()

                    if not text:
                        continue

                    style_name = item.style.name.lower() if item.style is not None else ""

                    is_heading = (
                        style_name.startswith("heading")
                        or style_name.startswith("título")
                        or style_name.startswith("titulo")
                    )

                    is_list = (
                        "list" in style_name
                        or "lista" in style_name
                        or (item._p.pPr is not None and item._p.pPr.numPr is not None)
                    )

                    if is_heading:
                        current_section = text
                        first_heading = first_heading or text
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
                            page_number=None,
                            section=current_section,
                            metadata={"style": item.style.name if item.style is not None else None},
                        )
                    )

                elif isinstance(item, Table):
                    table_text = self._extract_table(item)

                    if not table_text:
                        continue

                    blocks.append(
                        ExtractedBlock(
                            index=len(blocks),
                            text=table_text,
                            block_type="table",
                            page_number=None,
                            section=current_section,
                            metadata={
                                "rows": len(item.rows),
                                "columns": (len(item.columns) if item.columns else 0),
                            },
                        )
                    )

        except Exception as error:
            raise ExtractionError(
                "DOCX_EXTRACTION_ERROR",
                "No fue posible extraer el contenido del Word.",
            ) from error

        if not blocks:
            raise ExtractionError(
                "EMPTY_DOCX",
                "El documento Word no contiene texto extraíble.",
            )

        title = document.core_properties.title or first_heading

        return ExtractedDocument(
            title=title,
            page_count=None,
            blocks=blocks,
            metadata={
                "format": "docx",
                "pagination_preserved": False,
                "author": document.core_properties.author or None,
            },
        )

    def _iter_document_blocks(
        self,
        document: DocumentObject,
    ) -> Iterator[Paragraph | Table]:
        body = document.element.body

        for child in body.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, document)
            elif isinstance(child, CT_Tbl):
                yield Table(child, document)

    def _extract_table(self, table: Table) -> str:
        rows: list[str] = []

        for row in table.rows:
            cells = [" ".join(cell.text.split()) for cell in row.cells]

            if any(cells):
                rows.append(" | ".join(cells))

        return "\n".join(rows)
