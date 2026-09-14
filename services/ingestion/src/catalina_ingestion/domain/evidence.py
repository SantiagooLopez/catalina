import math
from dataclasses import dataclass
from enum import StrEnum

from catalina_ingestion.domain.retrieval import RetrievedChunk


class EvidenceReason(StrEnum):
    NO_RESULTS = "no_results"
    NO_RELEVANT_CHUNKS = "no_relevant_chunks"
    LOW_BEST_SCORE = "low_best_score"
    TOO_FEW_CHUNKS = "too_few_chunks"
    TOO_FEW_DOCUMENTS = "too_few_documents"
    TOO_LITTLE_TEXT = "too_little_text"
    PASSED_RETRIEVAL_CHECKS = "passed_retrieval_checks"


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    minimum_chunk_score: float = 0.50
    minimum_best_score: float = 0.54
    minimum_chunks: int = 1
    minimum_documents: int = 1
    minimum_characters: int = 80

    def __post_init__(self) -> None:
        for name in ("minimum_chunk_score", "minimum_best_score"):
            value = getattr(self, name)

            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} debe ser un número finito entre 0 y 1.")

        if self.minimum_best_score < self.minimum_chunk_score:
            raise ValueError("minimum_best_score no puede ser menor que minimum_chunk_score.")

        for name in (
            "minimum_chunks",
            "minimum_documents",
            "minimum_characters",
        ):
            value = getattr(self, name)

            if type(value) is not int or value < 1:
                raise ValueError(f"{name} debe ser un entero positivo.")


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    evidence_sufficient: bool
    reasons: tuple[EvidenceReason, ...]
    evaluated_chunks: int
    relevant_chunks: int
    document_count: int
    character_count: int
    best_score: float | None
    policy: EvidencePolicy


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    query: str
    chunks: tuple[RetrievedChunk, ...]
    assessment: EvidenceAssessment
