import hashlib

from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.extracted import ExtractedDocument
from catalina_ingestion.domain.processed import ProcessedDocument
from catalina_ingestion.processing.chunker import DocumentChunker
from catalina_ingestion.processing.structure import (
    StructureProcessor,
)


class DocumentProcessingService:
    def __init__(
        self,
        settings: Settings | None = None,
        structure_processor: StructureProcessor | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.structure_processor = structure_processor or StructureProcessor()
        self.chunker = DocumentChunker(
            target_size=self.settings.chunk_target_size,
            overlap=self.settings.chunk_overlap,
            minimum_size=self.settings.chunk_min_size,
        )

    def process(
        self,
        extracted: ExtractedDocument,
    ) -> ProcessedDocument:
        blocks, removed_count = self.structure_processor.process(extracted)

        chunks = self.chunker.create_chunks(blocks)

        canonical_content = "\n\n".join(block.text for block in blocks)

        content_sha256 = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        return ProcessedDocument(
            title=extracted.title,
            page_count=extracted.page_count,
            blocks=blocks,
            chunks=chunks,
            content_sha256=content_sha256,
            removed_repeated_blocks=removed_count,
            metadata={
                **extracted.metadata,
                "chunk_target_size": (self.settings.chunk_target_size),
                "chunk_overlap": self.settings.chunk_overlap,
                "chunk_minimum_size": (self.settings.chunk_min_size),
                "token_count_type": "estimated",
            },
        )
