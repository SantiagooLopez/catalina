from dataclasses import dataclass, field
from typing import Any

from catalina_ingestion.domain.extracted import BlockType


@dataclass(frozen=True, slots=True)
class ProcessedBlock:
    index: int
    source_index: int
    text: str
    block_type: BlockType
    page_number: int | None
    section: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    index: int
    text: str
    section: str | None
    page_start: int | None
    page_end: int | None
    source_block_indexes: tuple[int, ...]
    character_count: int
    estimated_tokens: int
    text_sha256: str


@dataclass(frozen=True, slots=True)
class ProcessedDocument:
    title: str | None
    page_count: int | None
    blocks: list[ProcessedBlock]
    chunks: list[DocumentChunk]
    content_sha256: str
    removed_repeated_blocks: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def section_count(self) -> int:
        return len({block.section for block in self.blocks if block.section is not None})
