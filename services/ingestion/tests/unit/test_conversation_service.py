from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
)
from catalina_ingestion.services.conversations import (
    ConversationService,
)


class AsyncContext:
    def __init__(
        self,
        value=None,
    ) -> None:
        self.value = value
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.value

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        self.exited = True
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.transactions: list[AsyncContext] = []

    def transaction(
        self,
    ) -> AsyncContext:
        context = AsyncContext()

        self.transactions.append(context)

        return context


class FakeConnectionFactory:
    def __init__(
        self,
        connection: FakeConnection,
    ) -> None:
        self.connection = connection
        self.calls = 0
        self.contexts: list[AsyncContext] = []

    def __call__(
        self,
    ) -> AsyncContext:
        self.calls += 1

        context = AsyncContext(self.connection)

        self.contexts.append(context)

        return context


def conversation(
    *,
    conversation_id: int = 10,
    user_id: int = 7,
    title: str = "Consulta académica",
) -> Conversation:
    started_at = datetime(
        2026,
        10,
        1,
        4,
        0,
        tzinfo=UTC,
    )

    updated_at = datetime(
        2026,
        10,
        1,
        4,
        5,
        tzinfo=UTC,
    )

    return Conversation(
        id=conversation_id,
        usuario_id=user_id,
        titulo=title,
        fecha_inicio=started_at,
        fecha_actualizacion=updated_at,
    )


def message(
    *,
    message_id: int = 20,
    conversation_id: int = 10,
) -> Message:
    return Message(
        id=message_id,
        conversacion_id=conversation_id,
        pregunta="Pregunta",
        respuesta="Respuesta",
        modelo=None,
        tiempo_respuesta=None,
        fecha=datetime.now(UTC),
    )


def build_service(
    *,
    conversations=None,
    messages=None,
):
    connection = FakeConnection()

    factory = FakeConnectionFactory(connection)

    conversation_repository = conversations or SimpleNamespace()

    message_repository = messages or SimpleNamespace()

    service = ConversationService(
        conversation_repository=(conversation_repository),
        message_repository=(message_repository),
        connection_factory=factory,
    )

    return (
        service,
        connection,
        factory,
    )


@pytest.mark.asyncio
async def test_create_conversation():
    expected = conversation()

    conversations = SimpleNamespace(create=AsyncMock(return_value=expected))

    service, connection, factory = build_service(conversations=conversations)

    result = await service.create_conversation(
        user_id=7,
        title="Consulta académica",
    )

    assert result == expected
    assert factory.calls == 1

    assert len(connection.transactions) == 1

    (
        conversations.create.assert_awaited_once_with(
            connection,
            usuario_id=7,
            titulo="Consulta académica",
        )
    )


@pytest.mark.asyncio
async def test_get_conversation():
    expected = conversation()

    conversations = SimpleNamespace(get_by_id=AsyncMock(return_value=expected))

    service, connection, _ = build_service(conversations=conversations)

    result = await service.get_conversation(
        user_id=7,
        conversation_id=10,
    )

    assert result == expected

    (
        conversations.get_by_id.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
        )
    )


@pytest.mark.asyncio
async def test_get_missing_conversation_raises():
    conversations = SimpleNamespace(get_by_id=AsyncMock(return_value=None))

    service, _, _ = build_service(conversations=conversations)

    with pytest.raises(ConversationNotFoundError):
        await service.get_conversation(
            user_id=7,
            conversation_id=10,
        )


@pytest.mark.asyncio
async def test_list_conversations():
    expected = [
        conversation(conversation_id=11),
        conversation(conversation_id=10),
    ]

    conversations = SimpleNamespace(list_by_user=AsyncMock(return_value=expected))

    service, connection, _ = build_service(conversations=conversations)

    result = await service.list_conversations(
        user_id=7,
        limit=25,
        offset=50,
    )

    assert result == expected

    (
        conversations.list_by_user.assert_awaited_once_with(
            connection,
            usuario_id=7,
            limit=25,
            offset=50,
        )
    )


@pytest.mark.asyncio
async def test_update_title():
    expected = conversation(title="Nuevo título")

    conversations = SimpleNamespace(update_title=AsyncMock(return_value=expected))

    service, connection, _ = build_service(conversations=conversations)

    result = await service.update_title(
        user_id=7,
        conversation_id=10,
        title="Nuevo título",
    )

    assert result == expected

    assert len(connection.transactions) == 1

    (
        conversations.update_title.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
            titulo="Nuevo título",
        )
    )


@pytest.mark.asyncio
async def test_update_missing_conversation_raises():
    conversations = SimpleNamespace(update_title=AsyncMock(return_value=None))

    service, _, _ = build_service(conversations=conversations)

    with pytest.raises(ConversationNotFoundError):
        await service.update_title(
            user_id=7,
            conversation_id=10,
            title="Nuevo título",
        )


@pytest.mark.asyncio
async def test_delete_conversation():
    conversations = SimpleNamespace(delete=AsyncMock(return_value=True))

    service, connection, _ = build_service(conversations=conversations)

    result = await service.delete_conversation(
        user_id=7,
        conversation_id=10,
    )

    assert result is None

    assert len(connection.transactions) == 1

    (
        conversations.delete.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
        )
    )


@pytest.mark.asyncio
async def test_delete_missing_conversation_raises():
    conversations = SimpleNamespace(delete=AsyncMock(return_value=False))

    service, _, _ = build_service(conversations=conversations)

    with pytest.raises(ConversationNotFoundError):
        await service.delete_conversation(
            user_id=7,
            conversation_id=10,
        )


@pytest.mark.asyncio
async def test_list_messages():
    expected_conversation = conversation()

    expected_messages = [
        message(message_id=20),
        message(message_id=21),
    ]

    conversations = SimpleNamespace(get_by_id=AsyncMock(return_value=(expected_conversation)))

    messages = SimpleNamespace(list_by_conversation=AsyncMock(return_value=expected_messages))

    service, connection, _ = build_service(
        conversations=conversations,
        messages=messages,
    )

    result = await service.list_messages(
        user_id=7,
        conversation_id=10,
        limit=25,
        offset=50,
    )

    assert result == expected_messages

    (
        conversations.get_by_id.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
        )
    )

    (
        messages.list_by_conversation.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
            limit=25,
            offset=50,
        )
    )


@pytest.mark.asyncio
async def test_list_messages_missing_conversation_raises():
    conversations = SimpleNamespace(get_by_id=AsyncMock(return_value=None))

    messages = SimpleNamespace(list_by_conversation=AsyncMock())

    service, _, _ = build_service(
        conversations=conversations,
        messages=messages,
    )

    with pytest.raises(ConversationNotFoundError):
        await service.list_messages(
            user_id=7,
            conversation_id=10,
        )

    (messages.list_by_conversation.assert_not_awaited())
