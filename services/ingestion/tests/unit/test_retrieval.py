import pytest

from catalina_ingestion.domain.retrieval import (
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
)


def test_retrieval_query_defaults() -> None:
    query = RetrievalQuery(query="¿Cuál es el reglamento estudiantil?")

    assert query.query == "¿Cuál es el reglamento estudiantil?"
    assert query.top_k == 5
    assert query.candidate_k == 20
    assert query.score_threshold == 0.50
    assert query.filters is None


def test_retrieval_query_accepts_filters() -> None:
    query = RetrievalQuery(
        query="¿Cuál es el horario?",
        filters=RetrievalFilter(
            category="academico",
            language="es",
        ),
    )

    assert query.filters is not None
    assert query.filters.category == "academico"
    assert query.filters.language == "es"


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
    ],
)
def test_retrieval_query_rejects_empty_query(query: str) -> None:
    with pytest.raises(ValueError, match="no puede estar vacía"):
        RetrievalQuery(query=query)


def test_retrieval_query_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError):
        RetrievalQuery(
            query="Pregunta válida",
            top_k=0,
        )


def test_retrieval_query_rejects_candidate_k_smaller_than_top_k() -> None:
    with pytest.raises(ValueError):
        RetrievalQuery(
            query="Pregunta válida",
            top_k=10,
            candidate_k=5,
        )


@pytest.mark.parametrize(
    "score_threshold",
    [
        -0.1,
        1.1,
    ],
)
def test_retrieval_query_rejects_invalid_score_threshold(
    score_threshold: float,
) -> None:
    with pytest.raises(ValueError):
        RetrievalQuery(
            query="Pregunta válida",
            score_threshold=score_threshold,
        )


def test_retrieval_result_count() -> None:
    chunk = RetrievedChunk(
        point_id="test-point",
        score=0.91,
        text="Contenido institucional de prueba.",
        document_id=1,
        document_version_id=1,
        document_name="Documento de prueba",
        version="1.0.0",
        category="faq",
        language="es",
        page_start=1,
        page_end=1,
        section=None,
        chunk_index=0,
        text_sha256="abc",
        content_sha256="def",
        embedding_model="embeddinggemma:latest",
    )

    result = RetrievalResult(
        query="Pregunta de prueba",
        chunks=(chunk,),
        total_candidates=5,
        evidence_sufficient=True,
        best_score=0.91,
    )

    assert result.count == 1
    assert result.best_score == 0.91
    assert result.evidence_sufficient is True
