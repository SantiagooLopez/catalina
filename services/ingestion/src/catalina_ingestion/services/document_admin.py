from collections.abc import Callable
from typing import Any

from fastapi import UploadFile

from catalina_ingestion.db.postgres import (
    postgres_connection,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    DocumentNotFoundError,
    ForbiddenError,
    VersionConflictError,
)
from catalina_ingestion.repositories.documents import (
    DocumentDetail,
    DocumentRepository,
    DocumentVersionDetail,
)
from catalina_ingestion.schemas.documents import (
    DocumentRegistrationRequest,
    DocumentRegistrationResult,
)
from catalina_ingestion.services.document_registration import (
    DocumentRegistrationService,
)
from catalina_ingestion.services.staging import (
    StagingService,
)


class DocumentAdminService:
    def __init__(
        self,
        *,
        repository: DocumentRepository | None = None,
        staging: StagingService | None = None,
        registration: (DocumentRegistrationService | None) = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self.repository = repository or DocumentRepository()

        self.staging = staging or StagingService()

        self.registration = registration or DocumentRegistrationService(
            repository=self.repository,
        )

        self.connection_factory = connection_factory

    @staticmethod
    def require_admin(
        current_user: AuthenticatedUser,
    ) -> None:
        if current_user.rol != "administrador":
            raise ForbiddenError

    async def register_document(
        self,
        *,
        current_user: AuthenticatedUser,
        upload: UploadFile,
        request: DocumentRegistrationRequest,
    ) -> DocumentRegistrationResult:
        self.require_admin(current_user)

        validated_file = await self.staging.receive(upload)

        return await self.registration.register(
            validated_file,
            request,
        )

    async def register_version(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
        upload: UploadFile,
        version: str,
    ) -> DocumentRegistrationResult:
        self.require_admin(current_user)

        document = await self.get_document(
            current_user=current_user,
            document_id=document_id,
        )

        if not document.codigo:
            raise VersionConflictError(
                "DOCUMENT_CODE_REQUIRED",
                ("El documento no tiene un código válido para registrar una versión."),
            )

        if not document.categoria:
            raise VersionConflictError(
                "DOCUMENT_CATEGORY_REQUIRED",
                ("El documento no tiene una categoría válida para registrar una versión."),
            )

        validated_file = await self.staging.receive(upload)

        request = DocumentRegistrationRequest(
            codigo=document.codigo,
            nombre=document.nombre,
            categoria=document.categoria,
            version=version,
            descripcion=document.descripcion,
            idioma=document.idioma,
            origen=document.origen,
            metadatos=document.metadatos,
        )

        result = await self.registration.register(
            validated_file,
            request,
        )

        if result.document_id != document_id:
            raise RuntimeError("La nueva versión fue asociada a un documento inesperado.")

        return result

    async def list_documents(
        self,
        *,
        current_user: AuthenticatedUser,
        limit: int,
        offset: int,
    ) -> list[DocumentDetail]:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.repository.list_documents(
                connection,
                limit=limit,
                offset=offset,
            )

    async def get_document(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
    ) -> DocumentDetail:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            document = await self.repository.get_document(
                connection,
                document_id,
            )

        if document is None:
            raise DocumentNotFoundError

        return document

    async def list_versions(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
        limit: int,
        offset: int,
    ) -> list[DocumentVersionDetail]:
        self.require_admin(current_user)

        await self.get_document(
            current_user=current_user,
            document_id=document_id,
        )

        async with self.connection_factory() as connection:
            return await self.repository.list_versions(
                connection,
                document_id=document_id,
                limit=limit,
                offset=offset,
            )

    async def set_status(
        self,
        *,
        current_user: AuthenticatedUser,
        document_id: int,
        status: str,
    ) -> DocumentDetail:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            async with connection.transaction():
                document = await self.repository.set_document_status(
                    connection,
                    document_id=document_id,
                    status=status,
                )

        if document is None:
            raise DocumentNotFoundError

        return document
