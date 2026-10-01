from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from catalina_ingestion.repositories.messages import (
    MessageRepository,
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


def message_row(
    *,
    message_id: int = 20,
    conversation_id: int = 10,
    pregunta: str = "¿Cuál es el calendario?",
    respuesta: str = "El calendario institucional...",
    modelo: str | None = "llama3.2:3b",
    tiempo_respuesta: Decimal | None = Decimal("1.245"),
) -> tuple[Any, ...]:
    created_at = datetime(
        2026,
        10,
        1,
        4,
        0,
        tzinfo=UTC,
    )

    return (
        message_id,
        conversation_id,
        pregunta,
        respuesta,
        modelo,
        tiempo_respuesta,
        created_at,
    )


@pytest.mark.asyncio
async def test_create_message_for_owned_conversation():
    connection = FakeConnection(FakeResult(row=message_row()))

    repository = MessageRepository()

    message = await repository.create(
        connection,
        conversation_id=10,
        usuario_id=7,
        pregunta="¿Cuál es el calendario?",
        respuesta="El calendario institucional...",
        modelo="llama3.2:3b",
        tiempo_respuesta=Decimal("1.245"),
    )

    assert message is not None
    assert message.id == 20
    assert message.conversacion_id == 10

    assert message.tiempo_respuesta == Decimal("1.245")

    query, params = connection.calls[0]

    assert "INSERT INTO catalina.mensajes" in query

    assert "FROM catalina.conversaciones c" in query

    assert "c.usuario_id = %s" in query

    assert params == (
        "¿Cuál es el calendario?",
        "El calendario institucional...",
        "llama3.2:3b",
        Decimal("1.245"),
        10,
        7,
    )


@pytest.mark.asyncio
async def test_create_returns_none_when_not_owned():
    connection = FakeConnection(FakeResult(row=None))

    repository = MessageRepository()

    message = await repository.create(
        connection,
        conversation_id=10,
        usuario_id=99,
        pregunta="Pregunta",
        respuesta="Respuesta",
    )

    assert message is None


@pytest.mark.asyncio
async def test_create_normalizes_text_fields():
    connection = FakeConnection(
        FakeResult(
            row=message_row(
                pregunta="Pregunta",
                respuesta="Respuesta",
                modelo="llama3.2:3b",
            )
        )
    )

    repository = MessageRepository()

    await repository.create(
        connection,
        conversation_id=10,
        usuario_id=7,
        pregunta="  Pregunta  ",
        respuesta="  Respuesta  ",
        modelo="  llama3.2:3b  ",
    )

    _, params = connection.calls[0]

    assert params == (
        "Pregunta",
        "Respuesta",
        "llama3.2:3b",
        None,
        10,
        7,
    )


@pytest.mark.asyncio
async def test_create_rejects_blank_question():
    connection = FakeConnection()

    repository = MessageRepository()

    with pytest.raises(
        ValueError,
        match="pregunta no puede estar vacío",
    ):
        await repository.create(
            connection,
            conversation_id=10,
            usuario_id=7,
            pregunta="   ",
            respuesta="Respuesta",
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_create_rejects_blank_answer():
    connection = FakeConnection()

    repository = MessageRepository()

    with pytest.raises(
        ValueError,
        match="respuesta no puede estar vacío",
    ):
        await repository.create(
            connection,
            conversation_id=10,
            usuario_id=7,
            pregunta="Pregunta",
            respuesta="   ",
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_create_rejects_negative_response_time():
    connection = FakeConnection()

    repository = MessageRepository()

    with pytest.raises(
        ValueError,
        match=("tiempo_respuesta no puede ser negativo"),
    ):
        await repository.create(
            connection,
            conversation_id=10,
            usuario_id=7,
            pregunta="Pregunta",
            respuesta="Respuesta",
            tiempo_respuesta=-0.5,
        )

    assert connection.calls == []


@pytest.mark.asyncio
async def test_get_by_id_for_owner():
    connection = FakeConnection(FakeResult(row=message_row()))

    repository = MessageRepository()

    message = await repository.get_by_id(
        connection,
        message_id=20,
        conversation_id=10,
        usuario_id=7,
    )

    assert message is not None
    assert message.id == 20
    assert message.conversacion_id == 10

    query, params = connection.calls[0]

    assert "JOIN catalina.conversaciones c" in query

    assert "c.usuario_id = %s" in query

    assert params == (
        20,
        10,
        7,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_owned():
    connection = FakeConnection(FakeResult(row=None))

    repository = MessageRepository()

    message = await repository.get_by_id(
        connection,
        message_id=20,
        conversation_id=10,
        usuario_id=99,
    )

    assert message is None


@pytest.mark.asyncio
async def test_list_by_conversation_is_paginated():
    connection = FakeConnection(
        FakeResult(
            rows=[
                message_row(
                    message_id=20,
                ),
                message_row(
                    message_id=21,
                    pregunta="Segunda pregunta",
                    respuesta="Segunda respuesta",
                ),
            ]
        )
    )

    repository = MessageRepository()

    messages = await repository.list_by_conversation(
        connection,
        conversation_id=10,
        usuario_id=7,
        limit=25,
        offset=50,
    )

    assert [message.id for message in messages] == [
        20,
        21,
    ]

    query, params = connection.calls[0]

    assert "JOIN catalina.conversaciones c" in query

    assert "m.fecha ASC" in query

    assert "m.id ASC" in query

    assert params == (
        10,
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
        (50, -1),
    ],
)
async def test_list_rejects_invalid_pagination(
    limit: int,
    offset: int,
):
    connection = FakeConnection()

    repository = MessageRepository()

    with pytest.raises(ValueError):
        await repository.list_by_conversation(
            connection,
            conversation_id=10,
            usuario_id=7,
            limit=limit,
            offset=offset,
        )

    assert connection.calls == []
