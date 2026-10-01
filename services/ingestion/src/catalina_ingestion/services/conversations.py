from collections.abc import Callable
from typing import Any

from catalina_ingestion.db.postgres import (
    postgres_connection,
)
from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
)
from catalina_ingestion.repositories.conversations import (
    DEFAULT_CONVERSATION_TITLE,
    ConversationRepository,
)
from catalina_ingestion.repositories.messages import (
    MessageRepository,
)


class ConversationService:
    def __init__(
        self,
        *,
        conversation_repository: (ConversationRepository | None) = None,
        message_repository: (MessageRepository | None) = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self._conversations = conversation_repository or ConversationRepository()

        self._messages = message_repository or MessageRepository()

        self._connection_factory = connection_factory

    async def create_conversation(
        self,
        *,
        user_id: int,
        title: str = DEFAULT_CONVERSATION_TITLE,
    ) -> Conversation:
        async with self._connection_factory() as connection:
            async with connection.transaction():
                return await self._conversations.create(
                    connection,
                    usuario_id=user_id,
                    titulo=title,
                )

    async def get_conversation(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> Conversation:
        async with self._connection_factory() as connection:
            conversation = await self._conversations.get_by_id(
                connection,
                conversation_id=(conversation_id),
                usuario_id=user_id,
            )

        if conversation is None:
            raise ConversationNotFoundError

        return conversation

    async def list_conversations(
        self,
        *,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        async with self._connection_factory() as connection:
            return await self._conversations.list_by_user(
                connection,
                usuario_id=user_id,
                limit=limit,
                offset=offset,
            )

    async def update_title(
        self,
        *,
        user_id: int,
        conversation_id: int,
        title: str,
    ) -> Conversation:
        async with self._connection_factory() as connection:
            async with connection.transaction():
                conversation = await self._conversations.update_title(
                    connection,
                    conversation_id=(conversation_id),
                    usuario_id=user_id,
                    titulo=title,
                )

        if conversation is None:
            raise ConversationNotFoundError

        return conversation

    async def delete_conversation(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> None:
        async with self._connection_factory() as connection:
            async with connection.transaction():
                deleted = await self._conversations.delete(
                    connection,
                    conversation_id=(conversation_id),
                    usuario_id=user_id,
                )

        if not deleted:
            raise ConversationNotFoundError

    async def list_messages(
        self,
        *,
        user_id: int,
        conversation_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        async with self._connection_factory() as connection:
            conversation = await self._conversations.get_by_id(
                connection,
                conversation_id=(conversation_id),
                usuario_id=user_id,
            )

            if conversation is None:
                raise ConversationNotFoundError

            return await self._messages.list_by_conversation(
                connection,
                conversation_id=(conversation_id),
                usuario_id=user_id,
                limit=limit,
                offset=offset,
            )
