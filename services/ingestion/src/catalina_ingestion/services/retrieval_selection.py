import math
import unicodedata
from collections import Counter
from dataclasses import replace

from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)
from catalina_ingestion.domain.search import (
    CandidateSearchResult,
    SearchError,
)
from catalina_ingestion.domain.selection import SelectedSearchResult
from catalina_ingestion.services.action_anchor_reranker import (
    ActionAnchorReranker,
)
from catalina_ingestion.services.vector_search import VectorSearchService


def validate_selection_query(query: RetrievalQuery) -> None:
    if type(query.top_k) is not int or type(query.candidate_k) is not int:
        raise ValueError("top_k y candidate_k deben ser enteros.")

    if not 1 <= query.top_k <= query.candidate_k <= 100:
        raise ValueError("Se requiere 1 <= top_k <= candidate_k <= 100.")

    threshold = query.score_threshold

    if (
        type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError("score_threshold debe ser un número finito entre 0 y 1.")


def validate_document_limit(limit: int | None) -> None:
    if limit is not None:
        if type(limit) is not int or limit < 1:
            raise ValueError("max_chunks_per_document debe ser un entero positivo o None.")


def canonical_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.split())


def duplicate_reference(chunk: RetrievedChunk) -> dict:
    return {
        "point_id": chunk.point_id,
        "document_id": chunk.document_id,
        "document_version_id": chunk.document_version_id,
        "document_name": chunk.document_name,
        "version": chunk.version,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "section": chunk.section,
        "index_run_id": chunk.metadata.get("index_run_id"),
        "score": chunk.score,
    }


def select_candidates(
    query: RetrievalQuery,
    candidates: CandidateSearchResult,
    *,
    max_chunks_per_document: int | None = 3,
    reranker: ActionAnchorReranker | None = None,
) -> SelectedSearchResult:
    validate_selection_query(query)
    validate_document_limit(max_chunks_per_document)

    if candidates.count > query.candidate_k:
        raise SearchError("El buscador devolvió más candidatos de los solicitados.")

    point_ids: set[str] = set()

    for chunk in candidates.chunks:
        if not math.isfinite(chunk.score):
            raise SearchError(f"Score no finito en el punto {chunk.point_id}.")

        if not canonical_text(chunk.text):
            raise SearchError(f"Texto vacío en el punto {chunk.point_id}.")

        if chunk.point_id in point_ids:
            raise SearchError(f"Identificador de punto repetido: {chunk.point_id}.")

        point_ids.add(chunk.point_id)

    eligible = [chunk for chunk in candidates.chunks if chunk.score >= query.score_threshold]

    # El score vectorial original sigue definiendo elegibilidad
    # y la representación de duplicados.
    eligible.sort(
        key=lambda chunk: (
            -chunk.score,
            chunk.point_id,
        )
    )

    groups: dict[str, list[RetrievedChunk]] = {}

    for chunk in eligible:
        key = canonical_text(chunk.text)
        groups.setdefault(
            key,
            [],
        ).append(chunk)

    unique: list[RetrievedChunk] = []

    for group in groups.values():
        # El primer elemento conserva siempre el mejor score
        # vectorial del grupo duplicado.
        representative = group[0]

        references = [duplicate_reference(chunk) for chunk in group[1:]]

        metadata = {
            **representative.metadata,
            "retrieval_duplicates": references,
        }

        unique.append(
            replace(
                representative,
                metadata=metadata,
            )
        )

    # El reranker solamente altera el orden.
    # Nunca modifica chunk.score.
    if reranker is not None:
        unique = list(
            reranker.rank(
                query.query,
                unique,
            )
        )

    counts: Counter[int] = Counter()
    diverse: list[RetrievedChunk] = []

    for chunk in unique:
        if (
            max_chunks_per_document is not None
            and counts[chunk.document_id] >= max_chunks_per_document
        ):
            continue

        diverse.append(chunk)
        counts[chunk.document_id] += 1

    selected = tuple(diverse[: query.top_k])

    return SelectedSearchResult(
        query=candidates.query,
        chunks=selected,
        candidate_count=candidates.count,
        removed_by_threshold=(candidates.count - len(eligible)),
        removed_duplicates=(len(eligible) - len(unique)),
        removed_by_diversity=(len(unique) - len(diverse)),
        removed_by_top_k=(len(diverse) - len(selected)),
    )


class RetrievalSelectionService:
    def __init__(
        self,
        search_service: VectorSearchService | None = None,
        *,
        max_chunks_per_document: int | None = 3,
        reranker: ActionAnchorReranker | None = None,
    ) -> None:
        validate_document_limit(max_chunks_per_document)

        self.search_service = search_service or VectorSearchService()

        self.max_chunks_per_document = max_chunks_per_document

        self.reranker = reranker

    async def search(
        self,
        query: RetrievalQuery,
    ) -> SelectedSearchResult:
        validate_selection_query(query)

        candidates = await self.search_service.search(query)

        return select_candidates(
            query,
            candidates,
            max_chunks_per_document=(self.max_chunks_per_document),
            reranker=self.reranker,
        )
