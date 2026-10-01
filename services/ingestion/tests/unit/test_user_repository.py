from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.repositories.users import (
    UserRepository,
)


def user_row():
    return (
        7,
        "usuario@ucatolica.edu.co",
        "Usuario Catalina",
        "usuario",
        "$argon2id$test-hash",
        True,
        datetime(
            2026,
            10,
            1,
            1,
            0,
        ),
        datetime(
            2026,
            10,
            1,
            1,
            0,
            tzinfo=UTC,
        ),
        None,
    )


@pytest.mark.asyncio
async def test_create_user():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=user_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.create(
        connection,
        email="  Usuario@UCATOLICA.EDU.CO ",
        nombre=" Usuario Catalina ",
        rol=" USUARIO ",
        password_hash=" $argon2id$test-hash ",
    )

    assert result.id == 7
    assert result.email == "usuario@ucatolica.edu.co"
    assert result.nombre == "Usuario Catalina"
    assert result.rol == "usuario"
    assert result.activo is True

    query, parameters = connection.execute.await_args.args

    assert "INSERT INTO catalina.usuarios" in query

    assert parameters == (
        "usuario@ucatolica.edu.co",
        "Usuario Catalina",
        "usuario",
        "$argon2id$test-hash",
    )


@pytest.mark.asyncio
async def test_get_user_by_id():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=user_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.get_by_id(
        connection,
        7,
    )

    assert result is not None
    assert result.id == 7
    assert result.rol == "usuario"

    _, parameters = connection.execute.await_args.args

    assert parameters == (7,)


@pytest.mark.asyncio
async def test_get_user_by_id_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.get_by_id(
        connection,
        999,
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_email_normalizes_email():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=user_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.get_by_email(
        connection,
        " Usuario@UCATOLICA.EDU.CO ",
    )

    assert result is not None
    assert result.id == 7

    query, parameters = connection.execute.await_args.args

    assert "LOWER(email) = %s" in query

    assert parameters == ("usuario@ucatolica.edu.co",)


@pytest.mark.asyncio
async def test_get_user_by_email_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.get_by_email(
        connection,
        "noexiste@ucatolica.edu.co",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_user_by_id_rejects_invalid_id():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = UserRepository()

    with pytest.raises(
        ValueError,
        match="user_id",
    ):
        await repository.get_by_id(
            connection,
            0,
        )

    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_user_by_email_rejects_blank_email():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = UserRepository()

    with pytest.raises(
        ValueError,
        match="email no puede estar vacío",
    ):
        await repository.get_by_email(
            connection,
            "   ",
        )

    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_rejects_blank_name():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = UserRepository()

    with pytest.raises(
        ValueError,
        match="nombre no puede estar vacío",
    ):
        await repository.create(
            connection,
            email="usuario@ucatolica.edu.co",
            nombre="   ",
            rol="usuario",
            password_hash="$argon2id$hash",
        )

    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_password_hash():
    row = list(user_row())
    row[4] = "$argon2id$new-hash"

    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=tuple(row)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.update_password_hash(
        connection,
        user_id=7,
        password_hash=" $argon2id$new-hash ",
    )

    assert result is not None
    assert result.password_hash == "$argon2id$new-hash"

    query, parameters = connection.execute.await_args.args

    assert "fecha_actualizacion = CURRENT_TIMESTAMP" in query

    assert parameters == (
        "$argon2id$new-hash",
        7,
    )


@pytest.mark.asyncio
async def test_update_password_hash_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.update_password_hash(
        connection,
        user_id=999,
        password_hash="$argon2id$new-hash",
    )

    assert result is None


@pytest.mark.asyncio
async def test_update_last_access():
    row = list(user_row())
    row[8] = datetime.now(UTC)

    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=tuple(row)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.update_last_access(
        connection,
        user_id=7,
    )

    assert result is not None
    assert result.ultimo_acceso is not None

    query, parameters = connection.execute.await_args.args

    assert "ultimo_acceso = CURRENT_TIMESTAMP" in query

    assert parameters == (7,)


@pytest.mark.asyncio
async def test_set_active():
    row = list(user_row())
    row[5] = False

    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=tuple(row)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.set_active(
        connection,
        user_id=7,
        active=False,
    )

    assert result is not None
    assert result.activo is False

    query, parameters = connection.execute.await_args.args

    assert "activo = %s" in query
    assert parameters == (
        False,
        7,
    )


@pytest.mark.asyncio
async def test_set_active_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = UserRepository()

    result = await repository.set_active(
        connection,
        user_id=999,
        active=False,
    )

    assert result is None


@pytest.mark.asyncio
async def test_set_active_rejects_non_boolean():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = UserRepository()

    with pytest.raises(
        TypeError,
        match="active debe ser booleano",
    ):
        await repository.set_active(
            connection,
            user_id=7,
            active=1,  # type: ignore[arg-type]
        )

    connection.execute.assert_not_awaited()
