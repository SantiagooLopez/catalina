from hashlib import sha256

import pytest

from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
    RetrievedChunk,
)
from catalina_ingestion.domain.search import CandidateSearchResult
from catalina_ingestion.services.retrieval_selection import (
    select_candidates,
)


def chunk(point_id, text, score, document_id=1):
    return RetrievedChunk(
        point_id=point_id,
        score=score,
        text=text,
        document_id=document_id,
        document_version_id=document_id,
        document_name=f"Documento {document_id}",
        version="1.0.0",
        category="faq",
        language="es",
        page_start=1,
        page_end=1,
        section=None,
        chunk_index=0,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        content_sha256="b" * 64,
        embedding_model="embeddinggemma:latest",
        metadata={"index_run_id": f"run-{document_id}"},
    )


def candidates(*items):
    return CandidateSearchResult(
        query="Consulta",
        chunks=tuple(items),
        returned_by_qdrant=len(items),
        discarded_after_recheck=0,
    )


def query(top_k=5):
    return RetrievalQuery(
        query="Consulta",
        top_k=top_k,
        candidate_k=20,
        score_threshold=0.70,
    )


def test_deduplicates_whitespace_and_keeps_best_source():
    original = candidates(
        chunk("a", "Horario de biblioteca", 0.80, 1),
        chunk("b", "  Horario   de\nbiblioteca ", 0.95, 2),
    )

    result = select_candidates(query(), original)

    assert result.count == 1
    assert result.chunks[0].point_id == "b"
    assert result.removed_duplicates == 1

    references = result.chunks[0].metadata["retrieval_duplicates"]
    assert len(references) == 1
    assert references[0]["point_id"] == "a"
    assert references[0]["document_id"] == 1

    assert "retrieval_duplicates" not in original.chunks[1].metadata


def test_deduplicates_equivalent_unicode():
    original = candidates(
        chunk("a", "Información académica", 0.90),
        chunk("b", "Informacio\u0301n acade\u0301mica", 0.80),
    )

    result = select_candidates(query(), original)

    assert result.count == 1
    assert result.removed_duplicates == 1


def test_keeps_different_numeric_information():
    result = select_candidates(
        query(),
        candidates(
            chunk("a", "El plazo es de 15 días.", 0.90),
            chunk("b", "El plazo es de 30 días.", 0.85),
        ),
    )

    assert result.count == 2
    assert result.removed_duplicates == 0


def test_applies_diversity_before_top_k():
    result = select_candidates(
        query(top_k=3),
        candidates(
            chunk("a", "Primer fragmento", 0.99, 1),
            chunk("b", "Segundo fragmento", 0.98, 1),
            chunk("c", "Tercer fragmento", 0.97, 1),
            chunk("d", "Cuarto fragmento", 0.90, 2),
        ),
        max_chunks_per_document=2,
    )

    assert [item.point_id for item in result.chunks] == ["a", "b", "d"]
    assert result.removed_by_diversity == 1
    assert result.removed_by_top_k == 0


def test_can_disable_document_limit():
    result = select_candidates(
        query(top_k=4),
        candidates(
            chunk("a", "Uno", 0.99),
            chunk("b", "Dos", 0.98),
            chunk("c", "Tres", 0.97),
            chunk("d", "Cuatro", 0.96),
        ),
        max_chunks_per_document=None,
    )

    assert result.count == 4
    assert result.removed_by_diversity == 0


def test_does_not_fill_results_with_discarded_chunks():
    result = select_candidates(
        query(top_k=5),
        candidates(
            chunk("a", "Uno", 0.99),
            chunk("b", "Dos", 0.98),
            chunk("c", "Tres", 0.97),
            chunk("d", "Cuatro", 0.96),
        ),
        max_chunks_per_document=2,
    )

    assert result.count == 2
    assert result.removed_by_diversity == 2


def test_discard_counts_account_for_every_candidate():
    result = select_candidates(
        query(top_k=1),
        candidates(
            chunk("a", "Texto A", 0.99, 1),
            chunk("b", "Texto A", 0.98, 2),
            chunk("c", "Texto B", 0.97, 1),
            chunk("d", "Texto C", 0.96, 2),
            chunk("e", "Texto D", 0.20, 3),
        ),
        max_chunks_per_document=1,
    )

    assert result.removed_by_threshold == 1
    assert result.removed_duplicates == 1
    assert result.removed_by_diversity == 1
    assert result.removed_by_top_k == 1
    assert result.count == 1

    assert result.candidate_count == (
        result.count
        + result.removed_by_threshold
        + result.removed_duplicates
        + result.removed_by_diversity
        + result.removed_by_top_k
    )


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_rejects_invalid_document_limit(limit):
    with pytest.raises(ValueError, match="max_chunks_per_document"):
        select_candidates(
            query(),
            candidates(),
            max_chunks_per_document=limit,
        )
