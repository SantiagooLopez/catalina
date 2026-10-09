from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IngestionJob:
    id: UUID
    document_version_id: int
    document_id: int
    document_code: str | None
    version: str
    type: str
    state: str
    progress: int
    attempt: int
    max_attempts: int
    priority: int
    configuration: dict[str, Any]
    worker_id: str | None
    locked_until: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
    error_code: str | None
    error_detail: str | None


@dataclass(frozen=True, slots=True)
class IndexingRun:
    id: UUID
    document_version_id: int
    document_id: int
    ingestion_job_id: UUID | None
    document_code: str | None
    version: str
    state: str
    qdrant_collection: str
    embedding_model: str
    embedding_dimension: int
    chunking_configuration: dict[str, Any]
    expected_chunks: int
    indexed_chunks: int
    attempt: int
    created_at: datetime
    activated_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
    error_code: str | None
    error_detail: str | None
