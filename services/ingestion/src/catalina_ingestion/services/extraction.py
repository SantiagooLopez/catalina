from pathlib import Path

from anyio.to_thread import run_sync

from catalina_ingestion.domain.extracted import ExtractedDocument
from catalina_ingestion.extractors.factory import ExtractorFactory


class ExtractionService:
    def __init__(
        self,
        factory: ExtractorFactory | None = None,
    ) -> None:
        self.factory = factory or ExtractorFactory()

    async def extract(
        self,
        path: Path,
        extension: str | None = None,
    ) -> ExtractedDocument:
        return await run_sync(
            self.factory.extract,
            path,
            extension,
        )
