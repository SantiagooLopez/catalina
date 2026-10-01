from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from catalina_ingestion.repositories.auth_sessions import (
    AuthSessionRepository,
)

SESSION_ID = UUID("11111111-2222-3333-4444-555555555555")

OLD_HASH = "a" * 64
NEW_HASH = "b" * 64


def session_row(
    *,
    refresh_hash: str = OLD_HASH,
):
    created_at = datetime(
        2026,
        10,
        1,
        1,
        0,
        tzinfo=UTC,
    )

    return (
        SESSION_ID,
        7,
        refresh_hash,
        created_at,
        created_at + timedelta(days=7),
        None,
        None,
        ip_address("127.0.0.1"),
        "pytest-agent",
    )


@pytest.mark.asyncio
async def test_create_auth_session():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=session_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    expires_at = datetime(
        2026,
        10,
        8,
        1,
        0,
        tzinfo=UTC,
    )

    result = await repository.create(
        connection,
        user_id=7,
        refresh_token_hash=OLD_HASH,
        expires_at=expires_at,
        ip="127.0.0.1",
        user_agent="pytest-agent",
    )

    assert result.id == SESSION_ID
    assert result.usuario_id == 7
    assert result.refresh_token_hash == OLD_HASH

    query, parameters = connection.execute.await_args.args

    assert "INSERT INTO catalina.sesiones_auth" in query

    assert parameters == (
        7,
        OLD_HASH,
        expires_at,
        "127.0.0.1",
        "pytest-agent",
    )


@pytest.mark.asyncio
async def test_get_auth_session_by_id():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=session_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.get_by_id(
        connection,
        SESSION_ID,
    )

    assert result is not None
    assert result.id == SESSION_ID

    _, parameters = connection.execute.await_args.args

    assert parameters == (SESSION_ID,)


@pytest.mark.asyncio
async def test_get_by_refresh_hash_normalizes_hash():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=session_row()))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.get_by_refresh_hash(
        connection,
        OLD_HASH.upper(),
    )

    assert result is not None

    _, parameters = connection.execute.await_args.args

    assert parameters == (OLD_HASH,)


@pytest.mark.asyncio
async def test_get_by_refresh_hash_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.get_by_refresh_hash(
        connection,
        OLD_HASH,
    )

    assert result is None


@pytest.mark.asyncio
async def test_rotate_refresh_token():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=session_row(refresh_hash=NEW_HASH)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    expires_at = datetime(
        2026,
        10,
        9,
        1,
        0,
        tzinfo=UTC,
    )

    result = await repository.rotate_refresh_token(
        connection,
        session_id=SESSION_ID,
        expected_refresh_token_hash=OLD_HASH,
        new_refresh_token_hash=NEW_HASH,
        expires_at=expires_at,
    )

    assert result is not None

    assert result.refresh_token_hash == NEW_HASH

    query, parameters = connection.execute.await_args.args

    assert "fecha_revocacion IS NULL" in query

    assert "fecha_expiracion > CURRENT_TIMESTAMP" in query

    assert "refresh_token_hash = %s" in query

    assert parameters == (
        NEW_HASH,
        expires_at,
        SESSION_ID,
        OLD_HASH,
    )


@pytest.mark.asyncio
async def test_rotate_refresh_token_returns_none():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.rotate_refresh_token(
        connection,
        session_id=SESSION_ID,
        expected_refresh_token_hash=OLD_HASH,
        new_refresh_token_hash=NEW_HASH,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    assert result is None


@pytest.mark.asyncio
async def test_revoke_auth_session():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=(SESSION_ID,)))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.revoke(
        connection,
        SESSION_ID,
    )

    assert result is True

    query, parameters = connection.execute.await_args.args

    assert "fecha_revocacion = CURRENT_TIMESTAMP" in query

    assert parameters == (SESSION_ID,)


@pytest.mark.asyncio
async def test_revoke_returns_false_if_not_updated():
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value=None))

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.revoke(
        connection,
        SESSION_ID,
    )

    assert result is False


@pytest.mark.asyncio
async def test_revoke_all_for_user():
    cursor = SimpleNamespace(rowcount=3)

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.revoke_all_for_user(
        connection,
        7,
    )

    assert result == 3

    _, parameters = connection.execute.await_args.args

    assert parameters == (7,)


@pytest.mark.asyncio
async def test_delete_expired_sessions():
    cursor = SimpleNamespace(rowcount=4)

    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    repository = AuthSessionRepository()

    result = await repository.delete_expired(connection)

    assert result == 4

    query = connection.execute.await_args.args[0]

    assert "fecha_expiracion" in query

    assert "CURRENT_TIMESTAMP" in query


@pytest.mark.asyncio
async def test_rejects_invalid_refresh_hash():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = AuthSessionRepository()

    with pytest.raises(
        ValueError,
        match="SHA-256",
    ):
        await repository.get_by_refresh_hash(
            connection,
            "hash-invalido",
        )

    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_all_rejects_invalid_user_id():
    connection = SimpleNamespace(execute=AsyncMock())

    repository = AuthSessionRepository()

    with pytest.raises(
        ValueError,
        match="user_id",
    ):
        await repository.revoke_all_for_user(
            connection,
            0,
        )

    connection.execute.assert_not_awaited()
