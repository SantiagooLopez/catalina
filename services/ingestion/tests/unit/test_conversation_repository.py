from datetime import UTC, datetime
from typing import Any

import pytest

from catalina_ingestion.repositories.conversations import (
    DEFAULT_CONVERSATION_TITLE,
    ConversationRepository,
)


class FakeResult:
    def __init__(
        self,
        *,
        row: Any = None,
        rows: list[Any] | None = None,
    ) -> None:
        self._row = row
        self._rows = rows if rows is not None else []

    async def fetchone(
        self,
    ) -> Any:
        return self._row

    async def fetchall(
        self,
    ) -> list[Any]:
        return self._rows


class FakeConnection:
    def __init__(
        self,
        *results: FakeResult,
    ) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(
        self,
        query: str,
        params: tuple[Any, ...],
    ) -> FakeResult:
        self.calls.append(
            (
                query,
                params,
            )
        )

        if not self.results:
            raise AssertionError("No hay más resultados falsos.")

        return self.results.pop(0)


def conversation_row(
    *,
    conversation_id: int = 10,
    usuario_id: int = 7,
    titulo: str = "Consulta académica",
) -> tuple[Any, ...]:
    started_at = datetime(
        2026,
        10,
        1,
        3,
        0,
        tzinfo=UTC,
    )

    updated_at = datetime(
        2026,
        10,
        1,
        3,
        5,
        tzinfo=UTC,
    )

    return (
        conversation_id,
        usuario_id,
        titulo,
        started_at,
        updated_at,
    )


@pytest.mark.asyncio
async def test_create_conversation():
    connection = FakeConnection(FakeResult(row=conversation_row()))

    repository = ConversationRepository()

    conversation = await repository.create(
        connection,
        usuario_id=7,
        titulo="  Consulta académica  ",
    )

    assert conversation.id == 10
    assert conversation.usuario_id == 7
    assert conversation.titulo == "Consulta académica"

    assert len(connection.calls) == 1

    query, params = connection.calls[0]

    assert "INSERT INTO catalina.conversaciones" in query

    assert params == (
        7,
        "Consulta académica",
    )


@pytest.mark.asyncio
async def test_create_uses_default_title():
    connection = FakeConnection(
        FakeResult(
            row=conversation_row(
                titulo=DEFAULT_CONVERSATION_TITLE,
            )
        )
    )

    repository = ConversationRepository()

    conversation = await repository.create(
        connection,
        usuario_id=7,
    )

    assert conversation.titulo == DEFAULT_CONVERSATION_TITLE

    _, params = connection.calls[0]

    assert params == (
        7,
        DEFAULT_CONVERSATION_TITLE,
    )


@pytest.mark.asyncio
async def test_create_rejects_blank_title():
    connection = FakeConnection()

    repository = ConversationRepository()

    with pytest.raises(
        ValueError,
        match="titulo no puede estar vacío",
    ):
        await repository.create(
            connection,
            usuario_id=7,
            titulo="   ",
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_get_by_id_for_owner():
    connection = FakeConnection(FakeResult(row=conversation_row()))

    repository = ConversationRepository()

    conversation = await repository.get_by_id(
        connection,
        conversation_id=10,
        usuario_id=7,
    )

    assert conversation is not None
    assert conversation.id == 10
    assert conversation.usuario_id == 7

    query, params = connection.calls[0]

    assert "id = %s" in query
    assert "usuario_id = %s" in query

    assert params == (
        10,
        7,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_owned():
    connection = FakeConnection(FakeResult(row=None))

    repository = ConversationRepository()

    conversation = await repository.get_by_id(
        connection,
        conversation_id=10,
        usuario_id=99,
    )

    assert conversation is None


@pytest.mark.asyncio
async def test_list_by_user_is_paginated():
    connection = FakeConnection(
        FakeResult(
            rows=[
                conversation_row(
                    conversation_id=12,
                    titulo="Segunda",
                ),
                conversation_row(
                    conversation_id=10,
                    titulo="Primera",
                ),
            ]
        )
    )

    repository = ConversationRepository()

    conversations = await repository.list_by_user(
        connection,
        usuario_id=7,
        limit=25,
        offset=50,
    )

    assert [conversation.id for conversation in conversations] == [
        12,
        10,
    ]

    query, params = connection.calls[0]

    assert "fecha_actualizacion DESC" in query

    assert "id DESC" in query

    assert params == (
        7,
        25,
        50,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (101, 0),
        (20, -1),
    ],
)
async def test_list_rejects_invalid_pagination(
    limit: int,
    offset: int,
):
    connection = FakeConnection()

    repository = ConversationRepository()

    with pytest.raises(ValueError):
        await repository.list_by_user(
            connection,
            usuario_id=7,
            limit=limit,
            offset=offset,
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_update_title_for_owner():
    connection = FakeConnection(
        FakeResult(
            row=conversation_row(
                titulo="Nuevo título",
            )
        )
    )

    repository = ConversationRepository()

    conversation = await repository.update_title(
        connection,
        conversation_id=10,
        usuario_id=7,
        titulo="  Nuevo título  ",
    )

    assert conversation is not None

    assert conversation.titulo == "Nuevo título"

    query, params = connection.calls[0]

    assert "UPDATE catalina.conversaciones" in query

    assert "fecha_actualizacion = CURRENT_TIMESTAMP" in query

    assert "usuario_id = %s" in query

    assert params == (
        "Nuevo título",
        10,
        7,
    )


@pytest.mark.asyncio
async def test_update_title_returns_none_when_not_owned():
    connection = FakeConnection(FakeResult(row=None))

    repository = ConversationRepository()

    conversation = await repository.update_title(
        connection,
        conversation_id=10,
        usuario_id=99,
        titulo="Nuevo título",
    )

    assert conversation is None


@pytest.mark.asyncio
async def test_update_title_rejects_blank_title():
    connection = FakeConnection()

    repository = ConversationRepository()

    with pytest.raises(
        ValueError,
        match="titulo no puede estar vacío",
    ):
        await repository.update_title(
            connection,
            conversation_id=10,
            usuario_id=7,
            titulo="   ",
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_touch_conversation():
    connection = FakeConnection(FakeResult(row=conversation_row()))

    repository = ConversationRepository()

    conversation = await repository.touch(
        connection,
        conversation_id=10,
        usuario_id=7,
    )

    assert conversation is not None
    assert conversation.id == 10

    query, params = connection.calls[0]

    assert "fecha_actualizacion = CURRENT_TIMESTAMP" in query

    assert "usuario_id = %s" in query

    assert params == (
        10,
        7,
    )


@pytest.mark.asyncio
async def test_delete_conversation_for_owner():
    connection = FakeConnection(FakeResult(row=(10,)))

    repository = ConversationRepository()

    deleted = await repository.delete(
        connection,
        conversation_id=10,
        usuario_id=7,
    )

    assert deleted is True

    query, params = connection.calls[0]

    assert "DELETE FROM catalina.conversaciones" in query

    assert "usuario_id = %s" in query
    assert "RETURNING id" in query

    assert params == (
        10,
        7,
    )


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_owned():
    connection = FakeConnection(FakeResult(row=None))

    repository = ConversationRepository()

    deleted = await repository.delete(
        connection,
        conversation_id=10,
        usuario_id=99,
    )

    assert deleted is False
