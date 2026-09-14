from dataclasses import dataclass

from catalina_ingestion.domain.embeddings import EmbeddingStatistics


@dataclass(frozen=True, slots=True)
class QueryEmbedding:
    original_query: str
    normalized_query: str
    model: str
    dimension: int
    vector: tuple[float, ...]
    statistics: EmbeddingStatistics
