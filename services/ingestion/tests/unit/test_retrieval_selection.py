from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)
from catalina_ingestion.domain.search import (
    CandidateSearchResult,
    SearchError,
)
from catalina_ingestion.services.action_anchor_reranker import (
    ActionAnchorReranker,
)
from catalina_ingestion.services.retrieval_selection import (
    RetrievalSelectionService,
    select_candidates,
)


def chunk(point_id, score):
    return RetrievedChunk(
        point_id=point_id,
        score=score,
        text=f"Contenido institucional de prueba {point_id}.",
        document_id=1,
        document_version_id=1,
        document_name="Guía institucional",
        version="1.0.0",
        category="faq",
        language="es",
        page_start=1,
        page_end=1,
        section=None,
        chunk_index=0,
        text_sha256="a" * 64,
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
    )


def candidates(*chunks):
    return CandidateSearchResult(
        query="Consulta de prueba",
        chunks=tuple(chunks),
        returned_by_qdrant=len(chunks),
        discarded_after_recheck=0,
    )


def test_orders_filters_and_limits_without_mutating_input():
    original = candidates(
        chunk("c", 0.70),
        chunk("b", 0.90),
        chunk("d", 0.69),
        chunk("a", 0.90),
    )
    query = RetrievalQuery(
        query="Consulta de prueba",
        top_k=2,
        candidate_k=4,
        score_threshold=0.70,
    )

    result = select_candidates(query, original)

    assert [item.point_id for item in result.chunks] == ["a", "b"]
    assert [item.point_id for item in original.chunks] == ["c", "b", "d", "a"]
    assert result.count == 2
    assert result.candidate_count == 4
    assert result.removed_by_threshold == 1
    assert result.removed_by_top_k == 1
    assert result.best_score == 0.90


def test_includes_score_equal_to_threshold():
    query = RetrievalQuery(
        query="Consulta",
        top_k=1,
        score_threshold=0.70,
    )

    result = select_candidates(
        query,
        candidates(chunk("a", 0.70)),
    )

    assert result.count == 1


def test_returns_empty_when_all_scores_are_below_threshold():
    query = RetrievalQuery(
        query="Consulta",
        score_threshold=0.70,
    )

    result = select_candidates(
        query,
        candidates(chunk("a", 0.29)),
    )

    assert result.count == 0
    assert result.best_score is None
    assert result.removed_by_threshold == 1
    assert result.removed_by_top_k == 0


def test_accepts_empty_candidates():
    result = select_candidates(
        RetrievalQuery(query="Consulta"),
        candidates(),
    )

    assert result.count == 0
    assert result.candidate_count == 0
    assert result.best_score is None


def test_rejects_non_finite_score():
    with pytest.raises(SearchError, match="no finito"):
        select_candidates(
            RetrievalQuery(query="Consulta"),
            candidates(chunk("a", float("nan"))),
        )


def test_rejects_excess_candidates():
    query = RetrievalQuery(
        query="Consulta",
        top_k=1,
        candidate_k=1,
    )

    with pytest.raises(SearchError, match="más candidatos"):
        select_candidates(
            query,
            candidates(chunk("a", 0.9), chunk("b", 0.8)),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"top_k": True},
        {"top_k": 1.5},
        {"candidate_k": 101},
        {"score_threshold": True},
    ],
)
async def test_rejects_invalid_parameters_before_search(changes):
    query = replace(
        RetrievalQuery(query="Consulta"),
        **changes,
    )
    search = SimpleNamespace(search=AsyncMock())
    service = RetrievalSelectionService(search_service=search)

    with pytest.raises(ValueError):
        await service.search(query)

    search.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_connects_search_with_selection():
    query = RetrievalQuery(
        query="Consulta",
        top_k=1,
        candidate_k=3,
    )
    search = SimpleNamespace(
        search=AsyncMock(
            return_value=candidates(
                chunk("a", 0.80),
                chunk("b", 0.95),
            )
        )
    )

    result = await RetrievalSelectionService(search_service=search).search(query)

    search.search.assert_awaited_once_with(query)
    assert result.count == 1
    assert result.chunks[0].point_id == "b"
    assert result.removed_by_top_k == 1


@pytest.mark.asyncio
async def test_applies_optional_action_anchor_reranker():
    query = RetrievalQuery(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        top_k=2,
        candidate_k=2,
        score_threshold=0.50,
    )

    original = replace(
        chunk(
            "original",
            0.781,
        ),
        document_id=7,
        document_version_id=7,
        document_name=("Calendario Académico de Pregrado 2026"),
        version="046-2025",
    )

    modification = replace(
        chunk(
            "modification",
            0.637,
        ),
        document_id=11,
        document_version_id=11,
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
        version="050-2026",
    )

    search = SimpleNamespace(
        search=AsyncMock(
            return_value=candidates(
                original,
                modification,
            )
        )
    )

    service = RetrievalSelectionService(
        search_service=search,
        reranker=ActionAnchorReranker(bonus=0.15),
    )

    result = await service.search(query)

    assert [item.point_id for item in result.chunks] == [
        "modification",
        "original",
    ]

    # El orden cambia, los scores no.
    assert result.chunks[0].score == 0.637
    assert result.chunks[1].score == 0.781


@pytest.mark.asyncio
async def test_default_selection_does_not_enable_reranker():
    query = RetrievalQuery(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        top_k=2,
        candidate_k=2,
        score_threshold=0.50,
    )

    original = replace(
        chunk(
            "original",
            0.781,
        ),
        document_id=7,
        document_name=("Calendario Académico de Pregrado 2026"),
    )

    modification = replace(
        chunk(
            "modification",
            0.637,
        ),
        document_id=11,
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
    )

    search = SimpleNamespace(
        search=AsyncMock(
            return_value=candidates(
                original,
                modification,
            )
        )
    )

    result = await RetrievalSelectionService(search_service=search).search(query)

    assert [item.point_id for item in result.chunks] == [
        "original",
        "modification",
    ]
