from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    DocumentNotFoundError,
    ForbiddenError,
)
from catalina_ingestion.repositories.documents import (
    DocumentDetail,
)
from catalina_ingestion.services.document_admin import (
    DocumentAdminService,
)


class AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeConnection:
    def transaction(self):
        return AsyncContext()


class ConnectionFactory:
    def __init__(self):
        self.connection = FakeConnection()

    def __call__(self):
        return AsyncContext(self.connection)


def current_user(
    *,
    role="administrador",
):
    return AuthenticatedUser(
        id=7,
        email="admin@catalina.local",
        nombre="Administrador",
        rol=role,
        activo=True,
    )


def document():
    now = datetime.now(UTC)

    return DocumentDetail(
        id=10,
        nombre="Documento prueba",
        tipo_archivo="TXT",
        categoria="faq",
        descripcion="Prueba",
        estado="activo",
        fecha_carga=now,
        codigo="documento-prueba",
        idioma="es",
        origen="E2E",
        metadatos={},
        fecha_actualizacion=now,
    )


@pytest.mark.asyncio
async def test_normal_user_cannot_list_documents():
    repository = SimpleNamespace(list_documents=AsyncMock())

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(ForbiddenError):
        await service.list_documents(
            current_user=current_user(role="usuario"),
            limit=20,
            offset=0,
        )

    repository.list_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_lists_documents():
    repository = SimpleNamespace(list_documents=AsyncMock(return_value=[document()]))

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    result = await service.list_documents(
        current_user=current_user(),
        limit=20,
        offset=0,
    )

    assert len(result) == 1
    assert result[0].id == 10


@pytest.mark.asyncio
async def test_admin_gets_document():
    repository = SimpleNamespace(get_document=AsyncMock(return_value=document()))

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    result = await service.get_document(
        current_user=current_user(),
        document_id=10,
    )

    assert result.id == 10


@pytest.mark.asyncio
async def test_missing_document_returns_error():
    repository = SimpleNamespace(get_document=AsyncMock(return_value=None))

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(DocumentNotFoundError):
        await service.get_document(
            current_user=current_user(),
            document_id=999999,
        )


@pytest.mark.asyncio
async def test_admin_changes_document_status():
    updated = document()

    repository = SimpleNamespace(set_document_status=AsyncMock(return_value=updated))

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    result = await service.set_status(
        current_user=current_user(),
        document_id=10,
        status="activo",
    )

    assert result.id == 10

    repository.set_document_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_missing_document():
    repository = SimpleNamespace(set_document_status=AsyncMock(return_value=None))

    service = DocumentAdminService(
        repository=repository,
        staging=SimpleNamespace(),
        registration=SimpleNamespace(),
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(DocumentNotFoundError):
        await service.set_status(
            current_user=current_user(),
            document_id=999999,
            status="inactivo",
        )
