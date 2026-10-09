from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    ForbiddenError,
)
from catalina_ingestion.domain.metrics import (
    IngestionMetrics,
    RagMetrics,
    SystemSummaryMetrics,
)
from catalina_ingestion.services.metrics import (
    MetricsService,
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


class Factory:
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


@pytest.mark.asyncio
async def test_normal_user_cannot_access_metrics():
    repository = SimpleNamespace(get_summary=AsyncMock())

    service = MetricsService(
        repository=repository,
        connection_factory=Factory(),
    )

    with pytest.raises(ForbiddenError):
        await service.get_summary(
            current_user=user("usuario"),
        )

    repository.get_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_gets_summary():
    expected = SystemSummaryMetrics(
        users_total=10,
        users_active=8,
        conversations_total=20,
        messages_total=50,
        documents_total=7,
        documents_active=6,
        documents_inactive=1,
        versions_total=9,
        versions_active=6,
        versions_pending=2,
        versions_failed=1,
    )

    repository = SimpleNamespace(get_summary=AsyncMock(return_value=expected))

    service = MetricsService(
        repository=repository,
        connection_factory=Factory(),
    )

    result = await service.get_summary(
        current_user=user(),
    )

    assert result == expected


@pytest.mark.asyncio
async def test_admin_gets_ingestion_metrics():
    expected = IngestionMetrics(
        jobs_total=10,
        jobs_pending=2,
        jobs_indexing=1,
        jobs_completed=6,
        jobs_failed=1,
        average_progress=Decimal("72.5"),
        indexing_runs_total=8,
        indexing_runs_preparing=1,
        indexing_runs_indexing=1,
        indexing_runs_verifying=1,
        indexing_runs_active=4,
        indexing_runs_failed=1,
    )

    repository = SimpleNamespace(get_ingestion_metrics=AsyncMock(return_value=expected))

    service = MetricsService(
        repository=repository,
        connection_factory=Factory(),
    )

    result = await service.get_ingestion_metrics(
        current_user=user(),
    )

    assert result == expected


@pytest.mark.asyncio
async def test_admin_gets_rag_metrics():
    expected = RagMetrics(
        messages_total=30,
        messages_with_model=25,
        messages_without_model=5,
        average_response_time_seconds=(Decimal("1.25")),
        metric_records=20,
        tokens_input_total=10000,
        tokens_output_total=5000,
        average_satisfaction=Decimal("4.5"),
        average_precision=Decimal("0.92"),
    )

    repository = SimpleNamespace(get_rag_metrics=AsyncMock(return_value=expected))

    service = MetricsService(
        repository=repository,
        connection_factory=Factory(),
    )

    result = await service.get_rag_metrics(
        current_user=user(),
    )

    assert result == expected
