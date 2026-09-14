from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IndexingContext:
    document_id: int
    document_version_id: int
    ingestion_job_id: UUID
    document_name: str
    version: str
    category: str
    language: str
    source_file: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkManifest:
    point_id: UUID
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section: str | None
    character_count: int
    estimated_tokens: int
    text_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IndexingResult:
    index_run_id: UUID
    point_count: int
    point_ids: tuple[UUID, ...]
    collection: str
    state: str
