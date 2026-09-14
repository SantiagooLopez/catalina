from pathlib import Path

from catalina_ingestion.domain.exceptions import ExtractionError
from catalina_ingestion.domain.extracted import ExtractedDocument
from catalina_ingestion.extractors.base import BaseExtractor
from catalina_ingestion.extractors.docx import DocxExtractor
from catalina_ingestion.extractors.html import HtmlExtractor
from catalina_ingestion.extractors.pdf import PdfExtractor
from catalina_ingestion.extractors.text import TextExtractor


class ExtractorFactory:
    def __init__(self) -> None:
        extractors: list[BaseExtractor] = [
            PdfExtractor(),
            DocxExtractor(),
            TextExtractor(),
            HtmlExtractor(),
        ]

        self._extractors = {
            extension: extractor
            for extractor in extractors
            for extension in extractor.supported_extensions
        }

    def get(self, extension: str) -> BaseExtractor:
        normalized = extension.lower()

        extractor = self._extractors.get(normalized)

        if extractor is None:
            raise ExtractionError(
                "EXTRACTOR_NOT_FOUND",
                f"No existe un extractor para {normalized}.",
            )

        return extractor

    def extract(
        self,
        path: Path,
        extension: str | None = None,
    ) -> ExtractedDocument:
        selected_extension = extension or path.suffix
        return self.get(selected_extension).extract(path)
