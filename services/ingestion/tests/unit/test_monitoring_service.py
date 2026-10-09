from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    DocumentNotFoundError,
    ForbiddenError,
    IndexingRunNotFoundError,
    IngestionJobNotFoundError,
)
from catalina_ingestion.domain.monitoring import (
    IndexingRun,
    IngestionJob,
)
from catalina_ingestion.services.monitoring import (
    MonitoringService,
)


class AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class ConnectionFactory:
    def __init__(self):
        self.connection = object()

    def __call__(self):
        return AsyncContext(self.connection)


def user(role="administrador"):
    return AuthenticatedUser(
        id=7,
        email="admin@catalina.local",
        nombre="Admin",
        rol=role,
        activo=True,
    )


def job():
    now = datetime.now(UTC)

    return IngestionJob(
        id=uuid4(),
        document_version_id=20,
        document_id=10,
        document_code="doc-test",
        version="1.0",
        type="ingesta",
        state="pendiente",
        progress=0,
        attempt=0,
        max_attempts=3,
        priority=0,
        configuration={},
        worker_id=None,
        locked_until=None,
        created_at=now,
        started_at=None,
        finished_at=None,
        updated_at=now,
        error_code=None,
        error_detail=None,
    )


def run():
    now = datetime.now(UTC)

    return IndexingRun(
        id=uuid4(),
        document_version_id=20,
        document_id=10,
        ingestion_job_id=uuid4(),
        document_code="doc-test",
        version="1.0",
        state="preparando",
        qdrant_collection="documentos_universidad",
        embedding_model="embeddinggemma",
        embedding_dimension=768,
        chunking_configuration={},
        expected_chunks=4,
        indexed_chunks=0,
        attempt=1,
        created_at=now,
        activated_at=None,
        finished_at=None,
        updated_at=now,
        error_code=None,
        error_detail=None,
    )


@pytest.mark.asyncio
async def test_normal_user_cannot_monitor():
    repository = SimpleNamespace(list_ingestion_jobs=AsyncMock())

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    with pytest.raises(ForbiddenError):
        await service.list_ingestion_jobs(
            current_user=user("usuario"),
            limit=50,
            offset=0,
        )

    repository.list_ingestion_jobs.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_lists_jobs():
    repository = SimpleNamespace(list_ingestion_jobs=AsyncMock(return_value=[job()]))

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    result = await service.list_ingestion_jobs(
        current_user=user(),
        limit=50,
        offset=0,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_missing_job():
    repository = SimpleNamespace(get_ingestion_job=AsyncMock(return_value=None))

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    with pytest.raises(IngestionJobNotFoundError):
        await service.get_ingestion_job(
            current_user=user(),
            job_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_admin_lists_runs():
    repository = SimpleNamespace(list_indexing_runs=AsyncMock(return_value=[run()]))

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    result = await service.list_indexing_runs(
        current_user=user(),
        limit=50,
        offset=0,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_missing_run():
    repository = SimpleNamespace(get_indexing_run=AsyncMock(return_value=None))

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    with pytest.raises(IndexingRunNotFoundError):
        await service.get_indexing_run(
            current_user=user(),
            run_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_missing_document_jobs():
    repository = SimpleNamespace(
        document_exists=AsyncMock(return_value=False),
        list_document_jobs=AsyncMock(),
    )

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    with pytest.raises(DocumentNotFoundError):
        await service.list_document_jobs(
            current_user=user(),
            document_id=999,
            limit=50,
            offset=0,
        )

    repository.list_document_jobs.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_jobs():
    expected = job()

    repository = SimpleNamespace(
        document_exists=AsyncMock(return_value=True),
        list_document_jobs=AsyncMock(return_value=[expected]),
    )

    service = MonitoringService(
        repository=repository,
        connection_factory=ConnectionFactory(),
    )

    result = await service.list_document_jobs(
        current_user=user(),
        document_id=10,
        limit=50,
        offset=0,
    )

    assert result == [expected]
