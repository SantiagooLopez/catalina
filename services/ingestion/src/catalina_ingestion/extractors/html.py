from pathlib import Path

from bs4 import BeautifulSoup, Tag
from charset_normalizer import from_bytes

from catalina_ingestion.domain.exceptions import ExtractionError
from catalina_ingestion.domain.extracted import (
    ExtractedBlock,
    ExtractedDocument,
)
from catalina_ingestion.extractors.base import BaseExtractor


class HtmlExtractor(BaseExtractor):
    supported_extensions = frozenset({".html", ".htm"})

    def extract(self, path: Path) -> ExtractedDocument:
        decoding_result = from_bytes(path.read_bytes()).best()

        if decoding_result is None:
            raise ExtractionError(
                "HTML_DECODING_ERROR",
                "No fue posible decodificar el HTML.",
            )

        soup = BeautifulSoup(str(decoding_result), "html.parser")

        for unwanted in soup(["script", "style", "noscript", "template"]):
            unwanted.decompose()

        blocks: list[ExtractedBlock] = []
        current_section: str | None = None
        heading_tags = {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }

        for element in soup.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "li",
                "table",
            ]
        ):
            if not isinstance(element, Tag):
                continue

            if element.name != "table" and element.find_parent("table") is not None:
                continue

            if element.name == "table":
                text = self._extract_table(element)
                block_type = "table"
            else:
                text = " ".join(element.get_text(" ", strip=True).split())

                if element.name in heading_tags:
                    block_type = "heading"
                    current_section = text
                elif element.name == "li":
                    block_type = "list"
                else:
                    block_type = "paragraph"

            if not text:
                continue

            blocks.append(
                ExtractedBlock(
                    index=len(blocks),
                    text=text,
                    block_type=block_type,
                    page_number=None,
                    section=current_section,
                    metadata={"html_tag": element.name},
                )
            )

        if not blocks:
            raise ExtractionError(
                "EMPTY_HTML",
                "El HTML no contiene bloques útiles.",
            )

        title = soup.title.get_text(" ", strip=True) if soup.title is not None else None

        if not title:
            title = next(
                (block.text for block in blocks if block.block_type == "heading"),
                path.stem,
            )

        html_element = soup.find("html")
        language = html_element.get("lang") if isinstance(html_element, Tag) else None

        return ExtractedDocument(
            title=title,
            page_count=None,
            blocks=blocks,
            metadata={
                "format": "html",
                "encoding": decoding_result.encoding,
                "language": language,
                "pagination_preserved": False,
            },
        )

    def _extract_table(self, table: Tag) -> str:
        rows: list[str] = []

        for row in table.find_all("tr"):
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in row.find_all(["th", "td"])
            ]

            if any(cells):
                rows.append(" | ".join(cells))

        return "\n".join(rows)
