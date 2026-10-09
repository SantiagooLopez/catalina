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


class GenerationError(IngestionError):
    """Error controlado durante la generación de respuestas."""


class TransientGenerationError(GenerationError):
    """Fallo temporal de generación que puede reintentarse."""


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


class AuthenticationError(IngestionError):
    """Error controlado durante autenticación."""


class InvalidCredentialsError(AuthenticationError):
    """Las credenciales proporcionadas no son válidas."""

    def __init__(self) -> None:
        super().__init__(
            "INVALID_CREDENTIALS",
            "Credenciales inválidas.",
        )


class InvalidRefreshTokenError(AuthenticationError):
    """El refresh token no es válido o ya no puede utilizarse."""

    def __init__(self) -> None:
        super().__init__(
            "INVALID_REFRESH_TOKEN",
            "Refresh token inválido o expirado.",
        )


class InvalidAccessTokenError(AuthenticationError):
    """El access token no es válido."""

    def __init__(self) -> None:
        super().__init__(
            "INVALID_ACCESS_TOKEN",
            "Access token inválido o expirado.",
        )


class ConversationNotFoundError(IngestionError):
    def __init__(self) -> None:
        super().__init__(
            code="CONVERSATION_NOT_FOUND",
            message="Conversación no encontrada.",
        )

class UserNotFoundError(IngestionError):
    def __init__(self) -> None:
        super().__init__(
            code="USER_NOT_FOUND",
            message="Usuario no encontrado.",
        )


class ForbiddenError(IngestionError):
    def __init__(self) -> None:
        super().__init__(
            code="FORBIDDEN",
            message=(
                "No tiene permisos para realizar "
                "esta operación."
            ),
        )


class InvalidCurrentPasswordError(
    IngestionError
):
    def __init__(self) -> None:
        super().__init__(
            code="INVALID_CURRENT_PASSWORD",
            message=(
                "La contraseña actual no es correcta."
            ),
        )
