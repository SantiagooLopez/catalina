from collections.abc import Callable
from typing import Any

from catalina_ingestion.db.postgres import (
    postgres_connection,
)
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
from catalina_ingestion.repositories.metrics import (
    MetricsRepository,
)


class MetricsService:
    def __init__(
        self,
        *,
        repository: MetricsRepository | None = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self.repository = repository or MetricsRepository()
        self.connection_factory = connection_factory

    @staticmethod
    def require_admin(
        current_user: AuthenticatedUser,
    ) -> None:
        if current_user.rol != "administrador":
            raise ForbiddenError

    async def get_summary(
        self,
        *,
        current_user: AuthenticatedUser,
    ) -> SystemSummaryMetrics:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.get_summary(connection)

    async def get_ingestion_metrics(
        self,
        *,
        current_user: AuthenticatedUser,
    ) -> IngestionMetrics:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.get_ingestion_metrics(connection)

    async def get_rag_metrics(
        self,
        *,
        current_user: AuthenticatedUser,
    ) -> RagMetrics:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.get_rag_metrics(connection)
