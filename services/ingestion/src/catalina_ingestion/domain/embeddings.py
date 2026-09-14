from dataclasses import dataclass

from catalina_ingestion.domain.processed import DocumentChunk


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: DocumentChunk
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingStatistics:
    batch_count: int
    input_count: int
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int


@dataclass(frozen=True, slots=True)
class TextEmbeddingBatch:
    model: str
    dimension: int
    vectors: tuple[tuple[float, ...], ...]
    statistics: EmbeddingStatistics


@dataclass(frozen=True, slots=True)
class EmbeddedDocument:
    model: str
    dimension: int
    chunks: list[EmbeddedChunk]
    statistics: EmbeddingStatistics
