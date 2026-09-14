from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.evidence import (
    EvidencePolicy,
    EvidenceReason,
)
from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)
from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.domain.selection import SelectedSearchResult
from catalina_ingestion.services.evidence import (
    EvidenceRetrievalService,
    assess_evidence,
)


def chunk(score=0.90, text=None):
    return RetrievedChunk(
        point_id="test-point",
        score=score,
        text=text
        if text is not None
        else (
            "La biblioteca atiende a los estudiantes en la sede "
            "principal. La información sobre sus servicios puede "
            "consultarse en el directorio institucional."
        ),
        document_id=1,
        document_version_id=1,
        document_name="Guía institucional",
        version="1.0.0",
        category="faq",
        language="es",
        page_start=1,
        page_end=1,
        section="Biblioteca",
        chunk_index=0,
        text_sha256="a" * 64,
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
    )


def selected(*chunks):
    return SelectedSearchResult(
        query="¿Dónde puedo consultar información de la biblioteca?",
        chunks=tuple(chunks),
        candidate_count=len(chunks),
        removed_by_threshold=0,
        removed_by_top_k=0,
    )


def test_accepts_relevant_context():
    result = assess_evidence(selected(chunk()))

    assert result.assessment.evidence_sufficient is True
    assert result.assessment.reasons == (EvidenceReason.PASSED_RETRIEVAL_CHECKS,)
    assert result.assessment.document_count == 1
    assert len(result.chunks) == 1


def test_rejects_empty_results():
    result = assess_evidence(selected())

    assert result.assessment.evidence_sufficient is False
    assert result.assessment.reasons == (EvidenceReason.NO_RESULTS,)
    assert result.assessment.best_score is None
    assert result.chunks == ()


def test_rejects_low_score_despite_permissive_search():
    result = assess_evidence(selected(chunk(score=0.293009)))

    assert result.assessment.evidence_sufficient is False
    assert result.assessment.reasons == (EvidenceReason.NO_RELEVANT_CHUNKS,)
    assert result.chunks == ()


def test_rejects_insufficient_best_score():
    result = assess_evidence(
        selected(chunk(score=0.72)),
        EvidencePolicy(
            minimum_chunk_score=0.70,
            minimum_best_score=0.75,
        ),
    )

    assert EvidenceReason.LOW_BEST_SCORE in result.assessment.reasons
    assert result.chunks == ()


def test_rejects_short_context():
    result = assess_evidence(selected(chunk(text="Biblioteca: sede principal.")))

    assert EvidenceReason.TOO_LITTLE_TEXT in result.assessment.reasons
    assert result.chunks == ()


def test_reports_multiple_policy_failures():
    result = assess_evidence(
        selected(chunk(score=0.72, text="Texto breve.")),
        EvidencePolicy(
            minimum_chunk_score=0.70,
            minimum_best_score=0.75,
            minimum_chunks=2,
            minimum_documents=2,
        ),
    )

    assert set(result.assessment.reasons) == {
        EvidenceReason.LOW_BEST_SCORE,
        EvidenceReason.TOO_FEW_CHUNKS,
        EvidenceReason.TOO_FEW_DOCUMENTS,
        EvidenceReason.TOO_LITTLE_TEXT,
    }


def test_accepts_exact_boundaries():
    result = assess_evidence(
        selected(chunk(score=0.75, text="Texto válido")),
        EvidencePolicy(minimum_characters=len("Texto válido")),
    )

    assert result.assessment.evidence_sufficient is True


@pytest.mark.parametrize(
    "values",
    [
        {"minimum_chunk_score": float("nan")},
        {"minimum_best_score": 1.1},
        {
            "minimum_chunk_score": 0.70,
            "minimum_best_score": 0.60,
        },
        {"minimum_chunks": 0},
        {"minimum_documents": True},
        {"minimum_characters": -1},
    ],
)
def test_rejects_invalid_policy(values):
    with pytest.raises(ValueError):
        EvidencePolicy(**values)


def test_corrupt_score_is_an_error():
    with pytest.raises(SearchError, match="no finito"):
        assess_evidence(selected(chunk(score=float("nan"))))


@pytest.mark.asyncio
async def test_propagates_infrastructure_failure():
    selection_service = SimpleNamespace(
        search=AsyncMock(side_effect=RuntimeError("Fallo de conexión simulado"))
    )
    service = EvidenceRetrievalService(selection_service=selection_service)

    with pytest.raises(RuntimeError, match="Fallo de conexión"):
        await service.search(RetrievalQuery(query="Consulta"))


@pytest.mark.asyncio
async def test_connects_selection_with_assessment():
    selection_service = SimpleNamespace(search=AsyncMock(return_value=selected(chunk())))
    service = EvidenceRetrievalService(selection_service=selection_service)
    query = RetrievalQuery(query="Consulta")

    result = await service.search(query)

    selection_service.search.assert_awaited_once_with(query)
    assert result.assessment.evidence_sufficient is True
