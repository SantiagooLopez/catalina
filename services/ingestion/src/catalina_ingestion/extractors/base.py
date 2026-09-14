from abc import ABC, abstractmethod
from pathlib import Path

from catalina_ingestion.domain.extracted import ExtractedDocument


class BaseExtractor(ABC):
    supported_extensions: frozenset[str] = frozenset()

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """Extrae la estructura y el contenido de un documento."""
