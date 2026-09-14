from pathlib import Path

from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.db.postgres import get_postgres_pool
from catalina_ingestion.domain.exceptions import (
    DuplicateFileError,
    VersionConflictError,
)
from catalina_ingestion.domain.files import ValidatedFile
from catalina_ingestion.repositories.documents import DocumentRepository
from catalina_ingestion.schemas.documents import (
    DocumentRegistrationRequest,
    DocumentRegistrationResult,
)
from catalina_ingestion.services.storage import DocumentStorageService


class DocumentRegistrationService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: DocumentRepository | None = None,
        storage: DocumentStorageService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or DocumentRepository()
        self.storage = storage or DocumentStorageService(self.settings)

    async def register(
        self,
        validated_file: ValidatedFile,
        request: DocumentRegistrationRequest,
    ) -> DocumentRegistrationResult:
        if request.categoria not in self.settings.allowed_categories:
            self.storage.discard_staging_file(validated_file.staging_path)
            raise VersionConflictError(
                "CATEGORY_NOT_ALLOWED",
                f"La categoría {request.categoria} no está permitida.",
            )

        pool = get_postgres_pool()
        final_path: Path | None = None

        try:
            async with pool.connection() as connection:
                async with connection.transaction():
                    duplicate = await self.repository.find_version_by_hash(
                        connection,
                        validated_file.sha256,
                    )

                    if duplicate is not None:
                        raise DuplicateFileError(
                            "DUPLICATE_FILE",
                            "El archivo ya se encuentra registrado.",
                            {
                                "document_id": duplicate.document_id,
                                "version_id": duplicate.version_id,
                                "version": duplicate.version,
                                "estado": duplicate.estado,
                            },
                        )

                    document = await self.repository.get_or_create_document(
                        connection,
                        request,
                        validated_file,
                    )

                    if not document.created and document.categoria != request.categoria:
                        raise VersionConflictError(
                            "DOCUMENT_CATEGORY_CONFLICT",
                            "El código ya pertenece a un documento de otra categoría.",
                            {
                                "document_id": document.id,
                                "existing_category": document.categoria,
                            },
                        )

                    existing_version = await self.repository.find_version_by_label(
                        connection,
                        document.id,
                        request.version,
                    )

                    if existing_version is not None:
                        raise VersionConflictError(
                            "VERSION_ALREADY_EXISTS",
                            "La versión indicada ya existe para el documento.",
                            {
                                "document_id": document.id,
                                "version_id": existing_version.version_id,
                                "version": existing_version.version,
                                "estado": existing_version.estado,
                            },
                        )

                    version_id = await self.repository.create_version(
                        connection,
                        document.id,
                        request,
                        validated_file,
                        self.settings,
                    )

                    final_path = await self.storage.persist(
                        validated_file,
                        request.categoria,
                        document.id,
                        version_id,
                    )

                    await self.repository.mark_version_pending(
                        connection,
                        version_id,
                        final_path,
                    )

                    job_id = await self.repository.create_ingestion_job(
                        connection,
                        version_id,
                        validated_file.sha256,
                        self.settings,
                    )

                    await self.repository.write_audit(
                        connection,
                        document.id,
                        version_id,
                        job_id,
                        validated_file.sha256,
                    )

            return DocumentRegistrationResult(
                document_id=document.id,
                document_version_id=version_id,
                ingestion_job_id=job_id,
                codigo=request.codigo,
                version=request.version,
                estado="pendiente",
                sha256=validated_file.sha256,
                storage_path=str(final_path),
            )

        except (DuplicateFileError, VersionConflictError):
            self.storage.discard_staging_file(validated_file.staging_path)
            raise
        except Exception:
            if final_path is not None:
                await self.storage.restore_to_staging(
                    final_path,
                    validated_file.staging_path,
                )
            raise
