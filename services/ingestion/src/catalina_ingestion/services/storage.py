from pathlib import Path

from anyio.to_thread import run_sync

from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.exceptions import StorageError
from catalina_ingestion.domain.files import ValidatedFile


class DocumentStorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def persist(
        self,
        validated_file: ValidatedFile,
        category: str,
        document_id: int,
        version_id: int,
    ) -> Path:
        if category not in self.settings.allowed_categories:
            raise StorageError(
                "CATEGORY_NOT_ALLOWED",
                f"La categoría {category} no está permitida.",
            )

        root = self.settings.documents_root.resolve()

        destination_directory = (root / category / str(document_id) / str(version_id)).resolve()

        if destination_directory != root and root not in destination_directory.parents:
            raise StorageError(
                "UNSAFE_STORAGE_PATH",
                "La ruta final está fuera del almacenamiento documental.",
            )

        destination_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )

        destination_name = f"{validated_file.sha256[:12]}_{validated_file.safe_name}"

        destination = destination_directory / destination_name

        if destination.exists():
            raise StorageError(
                "STORAGE_FILE_EXISTS",
                "Ya existe un archivo en la ruta definitiva.",
            )

        try:
            await run_sync(
                validated_file.staging_path.replace,
                destination,
            )
            destination.chmod(0o640)
        except Exception as error:
            raise StorageError(
                "STORAGE_MOVE_ERROR",
                "No fue posible mover el archivo al almacenamiento final.",
            ) from error

        return destination

    async def restore_to_staging(
        self,
        stored_path: Path,
        staging_path: Path,
    ) -> None:
        if not stored_path.exists():
            return

        staging_path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )

        await run_sync(
            stored_path.replace,
            staging_path,
        )

    def discard_staging_file(
        self,
        staging_path: Path,
    ) -> None:
        staging_path.unlink(missing_ok=True)
