from collections.abc import Callable
from typing import Any
from uuid import UUID

from catalina_ingestion.core.config import (
    Settings,
    get_settings,
)
from catalina_ingestion.db.postgres import (
    postgres_connection,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    DocumentNotFoundError,
    ForbiddenError,
    IngestionJobNotFoundError,
    JobControlConflictError,
)
from catalina_ingestion.domain.job_control import (
    JobActionResult,
)
from catalina_ingestion.repositories.documents import (
    DocumentRepository,
)
from catalina_ingestion.repositories.job_control import (
    JobControlRepository,
)


class JobControlService:
    def __init__(
        self,
        *,
        repository: JobControlRepository | None = None,
        document_repository: (DocumentRepository | None) = None,
        settings: Settings | None = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self.repository = repository or JobControlRepository()

        self.documents = document_repository or DocumentRepository()

        self.settings = settings or get_settings()

        self.connection_factory = connection_factory

    @staticmethod
    def require_admin(
        current_user: AuthenticatedUser,
    ) -> None:
        if current_user.rol != "administrador":
            raise ForbiddenError

    async def retry_job(
        self,
        *,
        current_user: AuthenticatedUser,
        job_id: UUID,
    ) -> JobActionResult:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            async with connection.transaction():
                job = await self.repository.get_job_for_update(
                    connection,
                    job_id,
                )

                if job is None:
                    raise IngestionJobNotFoundError

                if job.state != "fallido":
                    raise JobControlConflictError(
                        "JOB_NOT_FAILED",
                        ("Solo se pueden reintentar trabajos fallidos."),
                    )

                if job.attempt >= job.max_attempts:
                    raise JobControlConflictError(
                        "JOB_MAX_ATTEMPTS_REACHED",
                        ("El trabajo alcanzó el máximo de intentos permitidos."),
                    )

                await self.repository.reset_failed_job(
                    connection,
                    job.id,
                )

                await self.repository.write_retry_audit(
                    connection,
                    job=job,
                )

        return JobActionResult(
            job_id=job.id,
            document_id=job.document_id,
            document_version_id=(job.document_version_id),
            type=job.type,
            state="pendiente",
        )

    async def request_reindex(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
        version_id: int,
        reason: str,
    ) -> JobActionResult:
        self.require_admin(current_user)

        normalized_reason = reason.strip()

        if not normalized_reason:
            raise ValueError("reason no puede estar vacío.")

        async with self.connection_factory() as connection:
            async with connection.transaction():
                version = await self.repository.get_version_for_update(
                    connection,
                    document_id=document_id,
                    version_id=version_id,
                )

                if version is None:
                    raise DocumentNotFoundError

                if version.document_state != "activo":
                    raise JobControlConflictError(
                        "DOCUMENT_INACTIVE",
                        ("No se puede reindexar un documento inactivo."),
                    )

                if version.state != "activa":
                    raise JobControlConflictError(
                        "VERSION_NOT_ACTIVE",
                        ("Solo se puede solicitar reindexación de una versión activa."),
                    )

                if not version.file_hash:
                    raise JobControlConflictError(
                        "VERSION_FILE_HASH_MISSING",
                        ("La versión no tiene hash de archivo disponible."),
                    )

                existing = await self.repository.find_open_reindex_job(
                    connection,
                    version_id=version.id,
                )

                if existing is not None:
                    raise JobControlConflictError(
                        "REINDEX_ALREADY_PENDING",
                        ("Ya existe una reindexación pendiente o en ejecución para esta versión."),
                    )

                job_id = await self.documents.create_reindexing_job(
                    connection,
                    version.id,
                    version.file_hash,
                    self.settings,
                    normalized_reason,
                )

                await self.repository.write_reindex_audit(
                    connection,
                    job_id=job_id,
                    version=version,
                    reason=normalized_reason,
                )

        return JobActionResult(
            job_id=job_id,
            document_id=document_id,
            document_version_id=version_id,
            type="reindexacion",
            state="pendiente",
        )
