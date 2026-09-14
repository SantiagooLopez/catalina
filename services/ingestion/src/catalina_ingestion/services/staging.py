import hashlib
import re
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import UploadFile

from catalina_ingestion.core.config import Settings, get_settings
from catalina_ingestion.domain.exceptions import FileValidationError
from catalina_ingestion.domain.files import ValidatedFile
from catalina_ingestion.services.file_validation import FileValidator

READ_BLOCK_SIZE = 1024 * 1024


class StagingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.validator = FileValidator(self.settings)

    async def receive(self, upload: UploadFile) -> ValidatedFile:
        safe_name, extension = self.validator.validate_filename(upload.filename)

        self.settings.staging_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )

        temporary_path = self.settings.staging_directory / f"{uuid4()}.upload"

        maximum_bytes = self.settings.max_file_size_mb * 1024 * 1024
        size_bytes = 0
        sha256 = hashlib.sha256()

        try:
            destination = await anyio.open_file(
                temporary_path,
                mode="wb",
            )

            async with destination:
                while chunk := await upload.read(READ_BLOCK_SIZE):
                    size_bytes += len(chunk)

                    if size_bytes > maximum_bytes:
                        raise FileValidationError(
                            "FILE_TOO_LARGE",
                            "El archivo supera el tamaño máximo de "
                            f"{self.settings.max_file_size_mb} MB.",
                        )

                    sha256.update(chunk)
                    await destination.write(chunk)
        except FileValidationError:
            temporary_path.unlink(missing_ok=True)
            raise
        except Exception as error:
            temporary_path.unlink(missing_ok=True)
            raise FileValidationError(
                "FILE_WRITE_ERROR",
                "No fue posible guardar temporalmente el archivo.",
            ) from error
        finally:
            await upload.close()

        if size_bytes == 0:
            temporary_path.unlink(missing_ok=True)
            raise FileValidationError(
                "EMPTY_FILE",
                "El archivo recibido está vacío.",
            )

        temporary_path.chmod(0o640)

        try:
            inspection = self.validator.inspect(
                temporary_path,
                extension,
            )
        except FileValidationError as error:
            self._move_to_quarantine(temporary_path, error.code)
            raise

        return ValidatedFile(
            original_name=upload.filename or safe_name,
            safe_name=safe_name,
            extension=extension,
            mime_type=inspection.mime_type,
            client_mime_type=upload.content_type,
            encoding=inspection.encoding,
            size_bytes=size_bytes,
            sha256=sha256.hexdigest(),
            staging_path=temporary_path,
            page_count=inspection.page_count,
        )

    def _move_to_quarantine(
        self,
        source: Path,
        error_code: str,
    ) -> Path:
        self.settings.quarantine_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )

        safe_error_code = re.sub(
            r"[^A-Za-z0-9_-]",
            "_",
            error_code,
        ).lower()

        destination = self.settings.quarantine_directory / f"{source.stem}_{safe_error_code}.upload"

        source.replace(destination)
        destination.chmod(0o640)
        return destination
