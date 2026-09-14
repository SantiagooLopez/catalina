import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from psycopg import OperationalError

from catalina_ingestion.domain.retrieval import RetrievalQuery
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
    RetrievalRuntimePolicy,
)
from catalina_ingestion.domain.search import SearchError
from catalina_ingestion.services.retrieval_runtime import (
    ManagedRetrievalService,
)


def query():
    return RetrievalQuery(query="Consulta institucional")


def context():
    return SimpleNamespace(
        enabled=False,
        reason="insufficient_evidence",
    )


@pytest.mark.asyncio
async def test_insufficient_evidence_remains_a_normal_result():
    expected = context()
    service = ManagedRetrievalService(
        context_service=SimpleNamespace(build=AsyncMock(return_value=expected))
    )

    result = await service.build(query())

    assert result is expected
    assert result.enabled is False


@pytest.mark.asyncio
async def test_timeout_releases_capacity():
    stopped = asyncio.Event()

    async def slow_build(request):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    dependency = SimpleNamespace(build=AsyncMock(side_effect=slow_build))
    service = ManagedRetrievalService(
        context_service=dependency,
        policy=RetrievalRuntimePolicy(timeout_seconds=0.02),
    )

    with pytest.raises(RetrievalExecutionError) as captured:
        await service.build(query())

    assert captured.value.code == "RETRIEVAL_TIMEOUT"
    assert captured.value.retryable is True
    assert stopped.is_set()

    dependency.build.side_effect = None
    dependency.build.return_value = context()

    result = await service.build(query())
    assert result.enabled is False


@pytest.mark.asyncio
async def test_busy_rejection_and_cancellation_release_capacity():
    entered = asyncio.Event()

    async def blocked_build(request):
        entered.set()
        await asyncio.Event().wait()

    dependency = SimpleNamespace(build=AsyncMock(side_effect=blocked_build))
    service = ManagedRetrievalService(
        context_service=dependency,
        policy=RetrievalRuntimePolicy(
            timeout_seconds=5,
            max_concurrent=1,
        ),
    )

    first = asyncio.create_task(service.build(query()))

    try:
        await asyncio.wait_for(entered.wait(), timeout=1)

        with pytest.raises(RetrievalExecutionError) as captured:
            await service.build(query())

        assert captured.value.code == "RETRIEVAL_BUSY"
        assert captured.value.retryable is True
        assert dependency.build.await_count == 1
    finally:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    dependency.build.side_effect = None
    dependency.build.return_value = context()

    result = await service.build(query())
    assert result.enabled is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (
            OperationalError("Información técnica privada"),
            "DATABASE_UNAVAILABLE",
            True,
        ),
        (
            SearchError("Información técnica privada"),
            "RETRIEVAL_DATA_ERROR",
            False,
        ),
        (
            RuntimeError("Información técnica privada"),
            "RETRIEVAL_INTERNAL_ERROR",
            False,
        ),
        (
            TimeoutError("Información técnica privada"),
            "DEPENDENCY_TIMEOUT",
            True,
        ),
    ],
)
async def test_classifies_errors_without_exposing_original_message(error, code, retryable):
    service = ManagedRetrievalService(
        context_service=SimpleNamespace(build=AsyncMock(side_effect=error))
    )

    with pytest.raises(RetrievalExecutionError) as captured:
        await service.build(query())

    result = captured.value
    assert result.code == code
    assert result.retryable is retryable
    assert result.request_id
    assert "Información técnica privada" not in str(result)
    assert result.__cause__ is error


@pytest.mark.asyncio
async def test_invalid_input_does_not_start_retrieval():
    dependency = SimpleNamespace(build=AsyncMock())
    service = ManagedRetrievalService(context_service=dependency)

    with pytest.raises(RetrievalExecutionError) as captured:
        await service.build("Consulta")

    assert captured.value.code == "INVALID_QUERY"
    dependency.build.assert_not_awaited()


@pytest.mark.parametrize(
    "values",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"max_concurrent": 0},
        {"max_concurrent": True},
    ],
)
def test_rejects_invalid_runtime_policy(values):
    with pytest.raises(ValueError):
        RetrievalRuntimePolicy(**values)
