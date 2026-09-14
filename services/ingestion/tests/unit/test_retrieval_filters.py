import pytest
from qdrant_client import QdrantClient, models

from catalina_ingestion.domain.retrieval_filters import RetrievalFilter
from catalina_ingestion.services.retrieval_filters import (
    build_retrieval_filter,
)


@pytest.mark.parametrize(
    "values",
    [
        {"document_id": 0},
        {"document_id": -1},
        {"document_id": True},
        {"document_version_id": "1"},
        {"page_from": 0},
        {"page_to": 1.5},
        {"page_from": 5, "page_to": 2},
        {"category": "   "},
        {"language": 123},
        {"section": ""},
    ],
)
def test_rejects_invalid_filters(values):
    with pytest.raises(ValueError):
        RetrievalFilter(**values)


def test_trims_values_without_changing_case():
    filters = RetrievalFilter(
        category=" faq ",
        section=" Derechos del estudiante ",
    )

    assert filters.category == "faq"
    assert filters.section == "Derechos del estudiante"


def test_rejects_empty_authorized_scope():
    with pytest.raises(ValueError, match="ejecuciones autorizadas"):
        build_retrieval_filter([], "embeddinggemma:latest", None)


@pytest.fixture
def qdrant():
    client = QdrantClient(location=":memory:")
    client.create_collection(
        collection_name="filter_tests",
        vectors_config=models.VectorParams(
            size=3,
            distance=models.Distance.COSINE,
        ),
    )

    base = {
        "index_run_id": "active-run",
        "embedding_model": "embeddinggemma:latest",
        "document_id": 1,
        "document_version_id": 1,
        "category": "faq",
        "language": "es",
        "version": "1.0.0",
        "section": "Biblioteca",
        "page_start": 3,
        "page_end": 5,
    }

    payloads = [
        base,
        {**base, "category": "academico"},
        {**base, "index_run_id": "replaced-run"},
        {**base, "embedding_model": "another-model"},
        {**base, "page_start": 8, "page_end": 9},
        {**base, "section": None},
        {**base, "page_start": None, "page_end": None},
        {**base, "document_id": 2, "document_version_id": 2},
        {**base, "language": "en"},
        {**base, "version": "2.0.0"},
    ]

    try:
        client.upsert(
            collection_name="filter_tests",
            points=[
                models.PointStruct(
                    id=index,
                    vector=[1.0, 0.0, 0.0],
                    payload=payload,
                )
                for index, payload in enumerate(payloads, start=1)
            ],
            wait=True,
        )
        yield client
    finally:
        client.close()


def find_ids(client, filters):
    response = client.query_points(
        collection_name="filter_tests",
        query=[1.0, 0.0, 0.0],
        query_filter=build_retrieval_filter(
            ["active-run"],
            "embeddinggemma:latest",
            filters,
        ),
        limit=20,
    )
    return {point.id for point in response.points}


def test_combines_all_filters_and_preserves_active_scope(qdrant):
    ids = find_ids(
        qdrant,
        RetrievalFilter(
            document_id=1,
            document_version_id=1,
            category="faq",
            language="es",
            version="1.0.0",
            section="Biblioteca",
            page_from=4,
            page_to=4,
        ),
    )

    assert ids == {1}


def test_page_filter_matches_intersection_and_excludes_unknown(qdrant):
    ids = find_ids(
        qdrant,
        RetrievalFilter(page_from=4, page_to=4),
    )

    assert ids == {1, 2, 6, 8, 9, 10}


def test_conflicting_filters_return_no_results(qdrant):
    ids = find_ids(
        qdrant,
        RetrievalFilter(document_id=1, document_version_id=2),
    )

    assert ids == set()


def test_no_user_filters_still_excludes_replaced_runs(qdrant):
    ids = find_ids(qdrant, None)

    assert ids == {1, 2, 5, 6, 7, 8, 9, 10}
