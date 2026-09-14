import pytest

from catalina_ingestion.domain.retrieval import RetrievedChunk
from catalina_ingestion.services.action_anchor_reranker import (
    ActionAnchorReranker,
    extract_action_stems,
)


def chunk(
    point_id: str,
    score: float,
    *,
    document_name: str,
    section: str | None = None,
    text: str = "Contenido institucional.",
) -> RetrievedChunk:
    return RetrievedChunk(
        point_id=point_id,
        score=score,
        text=text,
        document_id=1,
        document_version_id=1,
        document_name=document_name,
        version="1.0.0",
        category="academico",
        language="es",
        page_start=1,
        page_end=1,
        section=section,
        chunk_index=0,
        text_sha256="a" * 64,
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
    )


def test_extracts_action_stems_from_inflected_words():
    assert extract_action_stems("¿Qué acuerdo modificó el calendario aprobado?") == frozenset(
        {
            "modific",
            "aprob",
        }
    )


def test_preserves_vector_order_without_action_anchor():
    reranker = ActionAnchorReranker()

    lower = chunk(
        "a",
        0.60,
        document_name="Documento A",
    )
    higher = chunk(
        "b",
        0.80,
        document_name="Documento B",
    )

    result = reranker.rank(
        "¿Cuál es el calendario académico?",
        (lower, higher),
    )

    assert [item.point_id for item in result] == ["b", "a"]


def test_promotes_document_matching_query_action():
    reranker = ActionAnchorReranker(
        bonus=0.15,
    )

    original = chunk(
        "original",
        0.781,
        document_name=("Calendario Académico de Pregrado 2026"),
    )

    modification = chunk(
        "modification",
        0.637,
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
    )

    result = reranker.rank(
        ("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        (
            original,
            modification,
        ),
    )

    assert result[0].point_id == "modification"

    # El reranker cambia el orden,
    # nunca el score vectorial original.
    assert result[0].score == 0.637
    assert result[1].score == 0.781


def test_matches_action_in_section():
    reranker = ActionAnchorReranker()

    original = chunk(
        "original",
        0.78,
        document_name="Calendario Académico",
    )

    modification = chunk(
        "modification",
        0.64,
        document_name="Acuerdo institucional",
        section=("Por el cual se modifica el Calendario Académico"),
    )

    result = reranker.rank(
        "¿Qué acuerdo modificó el calendario?",
        (
            original,
            modification,
        ),
    )

    assert result[0].point_id == "modification"


def test_does_not_use_body_text_as_action_anchor():
    reranker = ActionAnchorReranker()

    original = chunk(
        "original",
        0.80,
        document_name="Calendario Académico",
    )

    body_only = chunk(
        "body",
        0.70,
        document_name="Documento general",
        text=("Este documento modifica el calendario académico."),
    )

    result = reranker.rank(
        "¿Qué acuerdo modificó el calendario?",
        (
            original,
            body_only,
        ),
    )

    assert result[0].point_id == "original"


@pytest.mark.parametrize(
    "bonus",
    [
        -0.01,
        float("nan"),
        float("inf"),
        True,
    ],
)
def test_rejects_invalid_bonus(bonus):
    with pytest.raises(
        ValueError,
        match="bonus",
    ):
        ActionAnchorReranker(bonus=bonus)
