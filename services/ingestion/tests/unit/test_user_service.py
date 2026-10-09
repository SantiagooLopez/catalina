from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
    User,
)
from catalina_ingestion.domain.exceptions import (
    ForbiddenError,
    InvalidCurrentPasswordError,
    UserNotFoundError,
)
from catalina_ingestion.services.users import (
    UserService,
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


def make_user(
    *,
    user_id=7,
    role="usuario",
    active=True,
):
    now = datetime.now(UTC)

    return User(
        id=user_id,
        email="usuario@catalina.local",
        nombre="Usuario Catalina",
        rol=role,
        password_hash="hash",
        activo=active,
        fecha_creacion=now,
        fecha_actualizacion=now,
        ultimo_acceso=None,
    )


def make_authenticated(
    *,
    user_id=7,
    role="usuario",
):
    return AuthenticatedUser(
        id=user_id,
        email="usuario@catalina.local",
        nombre="Usuario Catalina",
        rol=role,
        activo=True,
    )


@pytest.mark.asyncio
async def test_update_own_name():
    updated = make_user()

    users = SimpleNamespace(update_name=AsyncMock(return_value=updated))

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    result = await service.update_own_name(
        current_user=make_authenticated(),
        nombre="Nuevo Nombre",
    )

    assert result == updated

    users.update_name.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_password():
    user = make_user()

    users = SimpleNamespace(
        get_by_id=AsyncMock(return_value=user),
        update_password_hash=AsyncMock(return_value=user),
    )

    passwords = SimpleNamespace(
        verify_and_update=lambda *args: SimpleNamespace(
            valid=True,
            updated_hash=None,
        ),
        hash_password=lambda password: "nuevo-hash",
    )

    service = UserService(
        user_repository=users,
        password_service=passwords,
        connection_factory=(ConnectionFactory()),
    )

    await service.change_own_password(
        current_user=make_authenticated(),
        current_password="Anterior123!",
        new_password="Nueva123!",
    )

    (users.update_password_hash.assert_awaited_once())


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_password():
    users = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_user()),
        update_password_hash=AsyncMock(),
    )

    passwords = SimpleNamespace(
        verify_and_update=lambda *args: SimpleNamespace(
            valid=False,
            updated_hash=None,
        ),
        hash_password=lambda password: "nuevo-hash",
    )

    service = UserService(
        user_repository=users,
        password_service=passwords,
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(InvalidCurrentPasswordError):
        await service.change_own_password(
            current_user=make_authenticated(),
            current_password="Incorrecta",
            new_password="Nueva123!",
        )

    (users.update_password_hash.assert_not_awaited())


@pytest.mark.asyncio
async def test_normal_user_cannot_list_users():
    users = SimpleNamespace(list_users=AsyncMock())

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(ForbiddenError):
        await service.list_users(
            current_user=make_authenticated(),
            limit=20,
            offset=0,
        )

    users.list_users.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_list_users():
    users = SimpleNamespace(list_users=AsyncMock(return_value=[make_user()]))

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    result = await service.list_users(
        current_user=make_authenticated(role="administrador"),
        limit=20,
        offset=0,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_admin_get_missing_user():
    users = SimpleNamespace(get_by_id=AsyncMock(return_value=None))

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    with pytest.raises(UserNotFoundError):
        await service.get_user(
            current_user=make_authenticated(role="administrador"),
            user_id=999,
        )


@pytest.mark.asyncio
async def test_admin_changes_role():
    updated = make_user(role="administrador")

    users = SimpleNamespace(update_role=AsyncMock(return_value=updated))

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    result = await service.set_user_role(
        current_user=make_authenticated(role="administrador"),
        user_id=7,
        role="administrador",
    )

    assert result.rol == "administrador"


@pytest.mark.asyncio
async def test_admin_changes_status():
    updated = make_user(active=False)

    users = SimpleNamespace(set_active=AsyncMock(return_value=updated))

    service = UserService(
        user_repository=users,
        connection_factory=(ConnectionFactory()),
    )

    result = await service.set_user_active(
        current_user=make_authenticated(role="administrador"),
        user_id=7,
        active=False,
    )

    assert result.activo is False
