from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.repositories.documents import (
    DocumentRepository,
)


def create_settings() -> Settings:
    return Settings(
        database_password="password-for-tests",
    )


@pytest.mark.asyncio
async def test_creates_reindexing_job():
    job_id = UUID("11111111-2222-3333-4444-555555555555")

    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=(job_id,)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    settings = create_settings()
    repository = DocumentRepository()

    sha256 = "a" * 64
    reason = "text-extractor-v2"

    result = await repository.create_reindexing_job(
        connection=connection,
        version_id=9,
        sha256=sha256,
        settings=settings,
        reason=reason,
    )

    assert result == job_id

    connection.execute.assert_awaited_once()

    query, parameters = connection.execute.await_args.args

    assert "'reindexacion'" in query
    assert "'pendiente'" in query

    assert parameters[0] == 9
    assert parameters[1] == settings.worker_max_attempts

    assert parameters[2] == (f"reindexacion:9:{sha256}:{reason}")

    configuration = parameters[3].obj

    assert configuration["embedding_model"] == settings.ollama_embedding_model

    assert configuration["embedding_dimension"] == settings.embedding_dimension

    assert configuration["chunk_target_size"] == settings.chunk_target_size

    assert configuration["chunk_overlap"] == settings.chunk_overlap

    assert configuration["chunk_min_size"] == settings.chunk_min_size

    assert configuration["reindex_reason"] == "text-extractor-v2"


@pytest.mark.asyncio
async def test_rejects_empty_reindexing_reason():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = DocumentRepository()

    with pytest.raises(
        ValueError,
        match="reason no puede estar vacío",
    ):
        await repository.create_reindexing_job(
            connection=connection,
            version_id=9,
            sha256="a" * 64,
            settings=create_settings(),
            reason="   ",
        )

    connection.execute.assert_not_awaited()
