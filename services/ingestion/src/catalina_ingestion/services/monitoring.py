from collections.abc import Callable
from typing import Any
from uuid import UUID

from catalina_ingestion.db.postgres import (
    postgres_connection,
)
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
from catalina_ingestion.repositories.monitoring import (
    MonitoringRepository,
)


class MonitoringService:
    def __init__(
        self,
        *,
        repository: MonitoringRepository | None = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self.repository = repository or MonitoringRepository()
        self.connection_factory = connection_factory

    @staticmethod
    def require_admin(
        current_user: AuthenticatedUser,
    ) -> None:
        if current_user.rol != "administrador":
            raise ForbiddenError

    async def list_ingestion_jobs(
        self,
        *,
        current_user: AuthenticatedUser,
        limit: int,
        offset: int,
    ) -> list[IngestionJob]:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.list_ingestion_jobs(
                connection,
                limit=limit,
                offset=offset,
            )

    async def get_ingestion_job(
        self,
        *,
        current_user: AuthenticatedUser,
        job_id: UUID,
    ) -> IngestionJob:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            job = await self.repository.get_ingestion_job(
                connection,
                job_id,
            )

        if job is None:
            raise IngestionJobNotFoundError

        return job

    async def list_document_jobs(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
        limit: int,
        offset: int,
    ) -> list[IngestionJob]:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            exists = await self.repository.document_exists(
                connection,
                document_id,
            )

            if not exists:
                raise DocumentNotFoundError

            return await self.repository.list_document_jobs(
                connection,
                document_id=document_id,
                limit=limit,
                offset=offset,
            )

    async def list_indexing_runs(
        self,
        *,
        current_user: AuthenticatedUser,
        limit: int,
        offset: int,
    ) -> list[IndexingRun]:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.list_indexing_runs(
                connection,
                limit=limit,
                offset=offset,
            )

    async def get_indexing_run(
        self,
        *,
        current_user: AuthenticatedUser,
        run_id: UUID,
    ) -> IndexingRun:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            run = await self.repository.get_indexing_run(
                connection,
                run_id,
            )

        if run is None:
            raise IndexingRunNotFoundError

        return run
