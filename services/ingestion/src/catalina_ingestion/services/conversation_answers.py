from collections.abc import Callable
from decimal import Decimal
from time import perf_counter_ns
from typing import Any

from catalina_ingestion.core.config import get_settings
from catalina_ingestion.db.postgres import (
    postgres_connection,
)
from catalina_ingestion.domain.conversation_answers import (
    ConversationAnswerResult,
)
from catalina_ingestion.domain.conversations import Message
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
)
from catalina_ingestion.domain.retrieval import (
    RetrievalQuery,
)
from catalina_ingestion.repositories.conversations import (
    ConversationRepository,
)
from catalina_ingestion.repositories.messages import (
    MessageRepository,
)
from catalina_ingestion.services.chat import (
    ChatService,
)

_NANOSECONDS_PER_SECOND = Decimal(1_000_000_000)


class ConversationAnswerService:
    def __init__(
        self,
        *,
        answer_service: (ChatService | None) = None,
        conversation_repository: (ConversationRepository | None) = None,
        message_repository: (MessageRepository | None) = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
        clock_ns: Callable[
            [],
            int,
        ] = perf_counter_ns,
    ) -> None:
        self._answer_service = answer_service or ChatService()

        self._conversations = conversation_repository or ConversationRepository()

        self._messages = message_repository or MessageRepository()

        self._connection_factory = connection_factory

        self._clock_ns = clock_ns

    async def answer(
        self,
        *,
        user_id: int,
        conversation_id: int,
        query: str,
    ) -> ConversationAnswerResult:
        history = await self._validate_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        started_ns = self._clock_ns()

        answer = await self._answer_service.answer(
            RetrievalQuery(
                query=query,
            ),
            history=history,
        )

        finished_ns = self._clock_ns()

        elapsed_ns = finished_ns - started_ns

        if elapsed_ns < 0:
            raise RuntimeError("El reloj monotónico produjo una duración negativa.")

        response_time = Decimal(elapsed_ns) / _NANOSECONDS_PER_SECOND

        async with self._connection_factory() as connection:
            async with connection.transaction():
                message = await self._messages.create(
                    connection,
                    conversation_id=(conversation_id),
                    usuario_id=user_id,
                    pregunta=answer.query,
                    respuesta=answer.text,
                    modelo=answer.model,
                    tiempo_respuesta=(response_time),
                )

                if message is None:
                    raise ConversationNotFoundError

                touched = await self._conversations.touch(
                    connection,
                    conversation_id=(conversation_id),
                    usuario_id=user_id,
                )

                if touched is None:
                    raise RuntimeError(
                        "La conversación desapareció durante la persistencia de la respuesta."
                    )

        return ConversationAnswerResult(
            answer=answer,
            message=message,
        )

    async def _validate_conversation(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> list[Message]:
        async with self._connection_factory() as connection:
            conversation = await self._conversations.get_by_id(
                connection,
                conversation_id=(conversation_id),
                usuario_id=user_id,
            )

            if conversation is None:
                raise ConversationNotFoundError
            return await self._messages.list_recent(
                connection,
                conversation_id=conversation_id,
                usuario_id=user_id,
                limit=get_settings().chat_history_turns,
            )
