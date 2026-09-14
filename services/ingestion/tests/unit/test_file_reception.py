from io import BytesIO

import pytest
from fastapi import UploadFile

from catalina_ingestion.core.config import Settings
from catalina_ingestion.domain.exceptions import FileValidationError
from catalina_ingestion.services.staging import StagingService


def create_settings(tmp_path, max_file_size_mb: int = 1) -> Settings:
    documents = tmp_path / "documents"

    return Settings(
        database_password="password-for-tests",
        documents_root=documents,
        staging_directory=documents / "staging",
        quarantine_directory=documents / "quarantine",
        max_file_size_mb=max_file_size_mb,
    )


@pytest.mark.asyncio
async def test_accepts_valid_text_file(tmp_path):
    settings = create_settings(tmp_path)
    service = StagingService(settings)

    upload = UploadFile(
        filename="reglamento.txt",
        file=BytesIO(b"Reglamento institucional de prueba."),
    )

    result = await service.receive(upload)

    assert result.original_name == "reglamento.txt"
    assert result.extension == ".txt"
    assert result.mime_type == "text/plain"
    assert result.size_bytes > 0
    assert len(result.sha256) == 64
    assert result.staging_path.exists()


@pytest.mark.asyncio
async def test_rejects_unsafe_filename(tmp_path):
    settings = create_settings(tmp_path)
    service = StagingService(settings)

    upload = UploadFile(
        filename="../../secreto.txt",
        file=BytesIO(b"contenido"),
    )

    with pytest.raises(FileValidationError) as captured:
        await service.receive(upload)

    assert captured.value.code == "UNSAFE_FILE_NAME"


@pytest.mark.asyncio
async def test_rejects_disallowed_extension(tmp_path):
    settings = create_settings(tmp_path)
    service = StagingService(settings)

    upload = UploadFile(
        filename="programa.exe",
        file=BytesIO(b"contenido"),
    )

    with pytest.raises(FileValidationError) as captured:
        await service.receive(upload)

    assert captured.value.code == "EXTENSION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_rejects_fake_pdf_and_quarantines_it(tmp_path):
    settings = create_settings(tmp_path)
    service = StagingService(settings)

    upload = UploadFile(
        filename="documento.pdf",
        file=BytesIO(b"Esto no es realmente un PDF"),
    )

    with pytest.raises(FileValidationError) as captured:
        await service.receive(upload)

    assert captured.value.code == "INVALID_PDF_SIGNATURE"

    quarantined = list(settings.quarantine_directory.iterdir())
    assert len(quarantined) == 1


@pytest.mark.asyncio
async def test_rejects_oversized_file(tmp_path):
    settings = create_settings(tmp_path, max_file_size_mb=1)
    service = StagingService(settings)

    upload = UploadFile(
        filename="archivo.txt",
        file=BytesIO(b"A" * (1024 * 1024 + 1)),
    )

    with pytest.raises(FileValidationError) as captured:
        await service.receive(upload)

    assert captured.value.code == "FILE_TOO_LARGE"
