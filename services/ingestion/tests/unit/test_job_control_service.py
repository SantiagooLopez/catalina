from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    ForbiddenError,
    IngestionJobNotFoundError,
    JobControlConflictError,
)
from catalina_ingestion.repositories.job_control import (
    ReindexableVersion,
    RetryableJob,
)
from catalina_ingestion.services.job_control import (
    JobControlService,
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


class FakeConnection:
    def transaction(self):
        return AsyncContext()


class Factory:
    def __init__(self):
        self.connection = FakeConnection()

    def __call__(self):
        return AsyncContext(self.connection)


def admin(role="administrador"):
    return AuthenticatedUser(
        id=7,
        email="admin@catalina.local",
        nombre="Admin",
        rol=role,
        activo=True,
    )


def failed_job(
    *,
    attempt=1,
    max_attempts=3,
    state="fallido",
):
    return RetryableJob(
        id=uuid4(),
        document_version_id=20,
        document_id=10,
        type="ingesta",
        state=state,
        attempt=attempt,
        max_attempts=max_attempts,
    )


@pytest.mark.asyncio
async def test_normal_user_cannot_retry():
    repository = SimpleNamespace(get_job_for_update=AsyncMock())

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(ForbiddenError):
        await service.retry_job(
            current_user=admin("usuario"),
            job_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_missing_job():
    repository = SimpleNamespace(get_job_for_update=AsyncMock(return_value=None))

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(IngestionJobNotFoundError):
        await service.retry_job(
            current_user=admin(),
            job_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_only_failed_job_can_retry():
    repository = SimpleNamespace(
        get_job_for_update=AsyncMock(return_value=failed_job(state="pendiente"))
    )

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(JobControlConflictError):
        await service.retry_job(
            current_user=admin(),
            job_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_max_attempts_blocks_retry():
    repository = SimpleNamespace(
        get_job_for_update=AsyncMock(
            return_value=failed_job(
                attempt=3,
                max_attempts=3,
            )
        )
    )

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(JobControlConflictError):
        await service.retry_job(
            current_user=admin(),
            job_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_failed_job_requeues():
    current = failed_job()

    repository = SimpleNamespace(
        get_job_for_update=AsyncMock(return_value=current),
        reset_failed_job=AsyncMock(),
        write_retry_audit=AsyncMock(),
    )

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    result = await service.retry_job(
        current_user=admin(),
        job_id=current.id,
    )

    assert result.job_id == current.id
    assert result.state == "pendiente"

    repository.reset_failed_job.assert_awaited_once()
    repository.write_retry_audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reindex_requires_active_version():
    repository = SimpleNamespace(
        get_version_for_update=AsyncMock(
            return_value=ReindexableVersion(
                id=20,
                document_id=10,
                document_state="activo",
                version="1.0",
                state="pendiente",
                file_hash="abc",
            )
        )
    )

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(JobControlConflictError):
        await service.request_reindex(
            current_user=admin(),
            document_id=10,
            version_id=20,
            reason="Prueba",
        )


@pytest.mark.asyncio
async def test_duplicate_reindex_is_blocked():
    repository = SimpleNamespace(
        get_version_for_update=AsyncMock(
            return_value=ReindexableVersion(
                id=20,
                document_id=10,
                document_state="activo",
                version="1.0",
                state="activa",
                file_hash="abc",
            )
        ),
        find_open_reindex_job=AsyncMock(return_value=uuid4()),
    )

    service = JobControlService(
        repository=repository,
        document_repository=SimpleNamespace(),
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    with pytest.raises(JobControlConflictError):
        await service.request_reindex(
            current_user=admin(),
            document_id=10,
            version_id=20,
            reason="Actualizar embeddings",
        )


@pytest.mark.asyncio
async def test_reindex_creates_job():
    repository = SimpleNamespace(
        get_version_for_update=AsyncMock(
            return_value=ReindexableVersion(
                id=20,
                document_id=10,
                document_state="activo",
                version="1.0",
                state="activa",
                file_hash="abc",
            )
        ),
        find_open_reindex_job=AsyncMock(return_value=None),
        write_reindex_audit=AsyncMock(),
    )

    new_job_id = uuid4()

    documents = SimpleNamespace(create_reindexing_job=AsyncMock(return_value=new_job_id))

    service = JobControlService(
        repository=repository,
        document_repository=documents,
        settings=SimpleNamespace(),
        connection_factory=Factory(),
    )

    result = await service.request_reindex(
        current_user=admin(),
        document_id=10,
        version_id=20,
        reason="Actualizar embeddings",
    )

    assert result.job_id == new_job_id
    assert result.type == "reindexacion"
    assert result.state == "pendiente"

    documents.create_reindexing_job.assert_awaited_once()
    repository.write_reindex_audit.assert_awaited_once()
