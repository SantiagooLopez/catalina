from dataclasses import dataclass

from catalina_ingestion.domain.retrieval import RetrievedChunk


@dataclass(frozen=True, slots=True)
class SelectedSearchResult:
    query: str
    chunks: tuple[RetrievedChunk, ...]
    candidate_count: int
    removed_by_threshold: int
    removed_by_top_k: int
    removed_duplicates: int = 0
    removed_by_diversity: int = 0

    @property
    def count(self) -> int:
        return len(self.chunks)

    @property
    def best_score(self) -> float | None:
        if not self.chunks:
            return None
        return self.chunks[0].score
