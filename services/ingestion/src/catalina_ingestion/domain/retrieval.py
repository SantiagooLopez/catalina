from dataclasses import dataclass, field
from typing import Any

from catalina_ingestion.domain.retrieval_filters import (
    RetrievalFilter as RetrievalFilter,
)


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    query: str
    top_k: int = 5
    candidate_k: int = 20
    score_threshold: float = 0.50
    filters: RetrievalFilter | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("La consulta no puede estar vacía.")

        if self.top_k < 1:
            raise ValueError("top_k debe ser mayor o igual a 1.")

        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k debe ser mayor o igual que top_k.")

        if not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold debe estar entre 0 y 1.")


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    point_id: str
    score: float
    text: str
    document_id: int
    document_version_id: int
    document_name: str
    version: str
    category: str
    language: str
    page_start: int | None
    page_end: int | None
    section: str | None
    chunk_index: int
    text_sha256: str
    content_sha256: str
    embedding_model: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    chunks: tuple[RetrievedChunk, ...]
    total_candidates: int
    evidence_sufficient: bool
    best_score: float | None

    @property
    def count(self) -> int:
        return len(self.chunks)
