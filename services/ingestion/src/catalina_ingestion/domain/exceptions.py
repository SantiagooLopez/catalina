from typing import Any


class IngestionError(Exception):
    """Error controlado del servicio de ingesta."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class FileValidationError(IngestionError):
    """Archivo rechazado durante su validación."""


class DuplicateFileError(IngestionError):
    """El archivo ya se encuentra registrado."""


class VersionConflictError(IngestionError):
    """La versión indicada ya existe con otro archivo."""


class StorageError(IngestionError):
    """Error en el almacenamiento definitivo."""


class ExtractionError(IngestionError):
    """Error controlado durante la extracción documental."""


class EmbeddingError(IngestionError):
    """Error controlado durante la generación de embeddings."""


class TransientEmbeddingError(EmbeddingError):
    """Fallo temporal que puede reintentarse."""


class IndexingError(IngestionError):
    """Error controlado durante la indexación vectorial."""
