from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from qdrant_client import models

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.services.vector_search import VectorSearchService


def build_service(initial_runs, current_runs, points):
    settings = Settings(
        _env_file=None,
        database_password="password-for-tests",
        ollama_embedding_model="embeddinggemma:latest",
        embedding_dimension=3,
        qdrant_collection="documentos_universidad",
    )

    repository = SimpleNamespace(active_runs=AsyncMock(side_effect=[initial_runs, current_runs]))

    client = SimpleNamespace(
        get_collection=AsyncMock(
            return_value=SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(
                        vectors=models.VectorParams(
                            size=3,
                            distance=models.Distance.COSINE,
                        )
                    )
                )
            )
        ),
        query_points=AsyncMock(return_value=SimpleNamespace(points=points)),
    )

    query_service = SimpleNamespace(
        normalize=lambda text: " ".join(text.split()),
        generate=AsyncMock(
            return_value=SimpleNamespace(
                normalized_query="¿Dónde está la biblioteca?",
                model="embeddinggemma:latest",
                dimension=3,
                vector=(0.1, 0.2, 0.3),
            )
        ),
    )

    service = VectorSearchService(
        settings=settings,
        client=client,
        repository=repository,
        query_service=query_service,
    )

    return service, client, repository, query_service


def create_point(run_id, **overrides):
    payload = {
        "schema_version": 1,
        "index_run_id": run_id,
        "document_id": 1,
        "document_version_id": 1,
        "document_name": "Guía institucional",
        "version": "1.0.0",
        "category": "faq",
        "language": "es",
        "page_start": 1,
        "page_end": 1,
        "section": None,
        "chunk_index": 0,
        "text": "La biblioteca se encuentra en la sede principal.",
        "text_sha256": "a" * 64,
        "content_sha256": "b" * 64,
        "embedding_model": "embeddinggemma:latest",
        "metadata": {},
    }
    payload.update(overrides)

    return models.ScoredPoint(
        id=str(uuid4()),
        version=0,
        score=0.85,
        payload=payload,
    )


def create_query():
    return RetrievalQuery(
        query="¿Dónde está la biblioteca?",
        score_threshold=0.70,
    )


@pytest.mark.asyncio
async def test_returns_active_chunk_and_filters_by_execution():
    run_id = str(uuid4())
    runs = {run_id: (1, 1)}
    point = create_point(run_id)

    service, client, repository, _ = build_service(runs, runs, [point])

    result = await service.search(create_query())

    assert result.count == 1
    assert result.returned_by_qdrant == 1
    assert result.discarded_after_recheck == 0

    chunk = result.chunks[0]
    assert chunk.point_id == point.id
    assert chunk.document_id == 1
    assert chunk.document_version_id == 1
    assert chunk.page_start == 1
    assert chunk.section is None
    assert chunk.metadata["index_run_id"] == run_id

    arguments = client.query_points.await_args.kwargs
    conditions = {condition.key: condition.match for condition in arguments["query_filter"].must}

    assert conditions["index_run_id"].any == [run_id]
    assert conditions["embedding_model"].value == "embeddinggemma:latest"
    assert arguments["score_threshold"] == 0.70
    assert arguments["with_payload"] is True
    assert arguments["with_vectors"] is False
    assert repository.active_runs.await_count == 2


@pytest.mark.asyncio
async def test_discards_execution_replaced_during_search():
    old_run = str(uuid4())
    new_run = str(uuid4())

    service, _, _, _ = build_service(
        {old_run: (1, 1)},
        {new_run: (1, 1)},
        [create_point(old_run)],
    )

    result = await service.search(create_query())

    assert result.count == 0
    assert result.returned_by_qdrant == 1
    assert result.discarded_after_recheck == 1


@pytest.mark.asyncio
async def test_rejects_point_outside_authorized_execution():
    active_run = str(uuid4())
    unauthorized_run = str(uuid4())
    runs = {active_run: (1, 1)}

    service, _, _, _ = build_service(
        runs,
        runs,
        [create_point(unauthorized_run)],
    )

    with pytest.raises(SearchError, match="alcance autorizado"):
        await service.search(create_query())


@pytest.mark.asyncio
async def test_rejects_mismatched_document_identity():
    run_id = str(uuid4())
    runs = {run_id: (1, 1)}

    service, _, _, _ = build_service(
        runs,
        runs,
        [create_point(run_id, document_id=99)],
    )

    with pytest.raises(SearchError, match="alcance autorizado"):
        await service.search(create_query())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"text": "   "},
        {"page_start": 5, "page_end": 2},
        {"text_sha256": "hash-invalido"},
        {"document_id": "1"},
    ],
)
async def test_rejects_invalid_payload(overrides):
    run_id = str(uuid4())
    runs = {run_id: (1, 1)}

    service, _, _, _ = build_service(
        runs,
        runs,
        [create_point(run_id, **overrides)],
    )

    with pytest.raises(SearchError, match="Payload inválido"):
        await service.search(create_query())


@pytest.mark.asyncio
async def test_returns_empty_without_calling_models_when_no_active_runs():
    service, client, repository, query_service = build_service({}, {}, [])

    result = await service.search(create_query())

    assert result.count == 0
    assert result.returned_by_qdrant == 0

    client.get_collection.assert_not_awaited()
    client.query_points.assert_not_awaited()
    query_service.generate.assert_not_awaited()
    assert repository.active_runs.await_count == 1


@pytest.mark.asyncio
async def test_database_failure_is_not_reported_as_empty_results():
    service, client, repository, _ = build_service({}, {}, [])
    repository.active_runs.side_effect = RuntimeError("Fallo de conexión simulado")

    with pytest.raises(RuntimeError, match="Fallo de conexión"):
        await service.search(create_query())

    client.query_points.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_incompatible_collection_before_embedding():
    run_id = str(uuid4())
    runs = {run_id: (1, 1)}
    service, client, _, query_service = build_service(runs, runs, [])

    client.get_collection.return_value.config.params.vectors = models.VectorParams(
        size=4,
        distance=models.Distance.COSINE,
    )

    with pytest.raises(SearchError, match="colección"):
        await service.search(create_query())

    query_service.generate.assert_not_awaited()
    client.query_points.assert_not_awaited()
