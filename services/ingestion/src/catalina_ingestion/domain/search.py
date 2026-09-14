from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalina_ingestion.domain.retrieval import RetrievedChunk


class SearchError(RuntimeError):
    pass


class IndexedPayload(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    schema_version: Literal[1]
    index_run_id: str
    document_id: int = Field(gt=0)
    document_version_id: int = Field(gt=0)
    document_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    category: str
    language: str
    page_start: int | None = Field(ge=1)
    page_end: int | None = Field(ge=1)
    section: str | None
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    embedding_model: str = Field(min_length=1)
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def validate_content(self) -> "IndexedPayload":
        UUID(self.index_run_id)

        if not self.text.strip():
            raise ValueError("El fragmento contiene solamente espacios.")

        if (self.page_start is None) != (self.page_end is None):
            raise ValueError("El rango de páginas está incompleto.")

        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("El rango de páginas está invertido.")

        return self


@dataclass(frozen=True, slots=True)
class CandidateSearchResult:
    query: str
    chunks: tuple[RetrievedChunk, ...]
    returned_by_qdrant: int
    discarded_after_recheck: int

    @property
    def count(self) -> int:
        return len(self.chunks)
