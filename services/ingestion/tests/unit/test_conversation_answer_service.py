from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalina_ingestion.domain.conversation_answers import (
    ConversationAnswerResult,
)
from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
    GenerationError,
)
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.services.conversation_answers import (
    ConversationAnswerService,
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

    def __call__(
        self,
    ) -> AsyncContext:
        self.calls += 1

        return AsyncContext(self.connection)


def make_conversation() -> Conversation:
    now = datetime.now(UTC)

    return Conversation(
        id=10,
        usuario_id=7,
        titulo="Consulta académica",
        fecha_inicio=now,
        fecha_actualizacion=now,
    )


def make_statistics() -> GenerationStatistics:
    return GenerationStatistics(
        total_duration_ns=900_000_000,
        load_duration_ns=10_000_000,
        prompt_eval_count=20,
        prompt_eval_duration_ns=200_000_000,
        eval_count=30,
        eval_duration_ns=600_000_000,
    )


def make_generated_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        query="¿Cuándo inicia el semestre?",
        text=("El semestre inicia según el calendario institucional."),
        generated=True,
        reason=GenerationReason.GENERATED,
        model="llama3.2:3b",
        citations=(),
        statistics=make_statistics(),
    )


def make_rejected_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        query="¿Hay sede en Cali?",
        text=(
            "No encontré evidencia institucional "
            "suficiente para responder esta "
            "pregunta con seguridad."
        ),
        generated=False,
        reason=(GenerationReason.INSUFFICIENT_EVIDENCE),
        model=None,
        citations=(),
        statistics=None,
    )


def make_message(
    *,
    question: str,
    answer: str,
    model: str | None,
    response_time: Decimal,
) -> Message:
    return Message(
        id=20,
        conversacion_id=10,
        pregunta=question,
        respuesta=answer,
        modelo=model,
        tiempo_respuesta=response_time,
        fecha=datetime.now(UTC),
    )


def build_service(
    *,
    answer_service,
    conversations,
    messages,
    clock_values=(
        1_000_000_000,
        2_500_000_000,
    ),
):
    connection = FakeConnection()

    factory = FakeConnectionFactory(connection)

    values = iter(clock_values)

    service = ConversationAnswerService(
        answer_service=answer_service,
        conversation_repository=(conversations),
        message_repository=messages,
        connection_factory=factory,
        clock_ns=lambda: next(values),
    )

    return (
        service,
        connection,
        factory,
    )


@pytest.mark.asyncio
async def test_generated_answer_is_persisted():
    generated = make_generated_answer()

    stored_message = make_message(
        question=generated.query,
        answer=generated.text,
        model=generated.model,
        response_time=Decimal("1.5"),
    )

    answer_service = SimpleNamespace(answer=AsyncMock(return_value=generated))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(return_value=make_conversation()),
    )

    messages = SimpleNamespace(create=AsyncMock(return_value=stored_message))

    service, connection, factory = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    result = await service.answer(
        user_id=7,
        conversation_id=10,
        query=generated.query,
    )

    assert isinstance(
        result,
        ConversationAnswerResult,
    )

    assert result.answer == generated
    assert result.message == stored_message

    assert factory.calls == 2

    assert len(connection.transactions) == 1

    (
        conversations.get_by_id.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
        )
    )

    query_argument = answer_service.answer.await_args.args[0]

    assert query_argument.query == generated.query

    (
        messages.create.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
            pregunta=generated.query,
            respuesta=generated.text,
            modelo="llama3.2:3b",
            tiempo_respuesta=Decimal("1.5"),
        )
    )

    (
        conversations.touch.assert_awaited_once_with(
            connection,
            conversation_id=10,
            usuario_id=7,
        )
    )


@pytest.mark.asyncio
async def test_non_generated_safe_answer_is_persisted():
    rejected = make_rejected_answer()

    stored_message = make_message(
        question=rejected.query,
        answer=rejected.text,
        model=None,
        response_time=Decimal("1.5"),
    )

    answer_service = SimpleNamespace(answer=AsyncMock(return_value=rejected))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(return_value=make_conversation()),
    )

    messages = SimpleNamespace(create=AsyncMock(return_value=stored_message))

    service, _, _ = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    result = await service.answer(
        user_id=7,
        conversation_id=10,
        query=rejected.query,
    )

    assert result.answer.generated is False
    assert result.message.modelo is None

    (messages.create.assert_awaited_once())

    kwargs = messages.create.await_args.kwargs

    assert kwargs["modelo"] is None

    assert kwargs["tiempo_respuesta"] == Decimal("1.5")


@pytest.mark.asyncio
async def test_missing_conversation_blocks_rag():
    answer_service = SimpleNamespace(answer=AsyncMock())

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None),
        touch=AsyncMock(),
    )

    messages = SimpleNamespace(create=AsyncMock())

    service, _, factory = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    with pytest.raises(ConversationNotFoundError):
        await service.answer(
            user_id=99,
            conversation_id=10,
            query="Pregunta",
        )

    assert factory.calls == 1

    (answer_service.answer.assert_not_awaited())

    messages.create.assert_not_awaited()
    conversations.touch.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_error_does_not_persist():
    generation_error = GenerationError(
        "GENERATION_TEST_ERROR",
        "Fallo de generación.",
        {},
    )

    answer_service = SimpleNamespace(answer=AsyncMock(side_effect=generation_error))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(),
    )

    messages = SimpleNamespace(create=AsyncMock())

    service, _, factory = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    with pytest.raises(GenerationError):
        await service.answer(
            user_id=7,
            conversation_id=10,
            query="Pregunta",
        )

    assert factory.calls == 1

    messages.create.assert_not_awaited()
    conversations.touch.assert_not_awaited()


@pytest.mark.asyncio
async def test_conversation_disappears_before_persistence():
    generated = make_generated_answer()

    answer_service = SimpleNamespace(answer=AsyncMock(return_value=generated))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(),
    )

    messages = SimpleNamespace(create=AsyncMock(return_value=None))

    service, connection, factory = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    with pytest.raises(ConversationNotFoundError):
        await service.answer(
            user_id=7,
            conversation_id=10,
            query=generated.query,
        )

    assert factory.calls == 2

    assert len(connection.transactions) == 1

    conversations.touch.assert_not_awaited()


@pytest.mark.asyncio
async def test_touch_failure_raises_and_aborts():
    generated = make_generated_answer()

    stored_message = make_message(
        question=generated.query,
        answer=generated.text,
        model=generated.model,
        response_time=Decimal("1.5"),
    )

    answer_service = SimpleNamespace(answer=AsyncMock(return_value=generated))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(return_value=None),
    )

    messages = SimpleNamespace(create=AsyncMock(return_value=stored_message))

    service, connection, _ = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
    )

    with pytest.raises(
        RuntimeError,
        match="desapareció",
    ):
        await service.answer(
            user_id=7,
            conversation_id=10,
            query=generated.query,
        )

    assert len(connection.transactions) == 1


@pytest.mark.asyncio
async def test_negative_elapsed_time_is_rejected():
    generated = make_generated_answer()

    answer_service = SimpleNamespace(answer=AsyncMock(return_value=generated))

    conversations = SimpleNamespace(
        get_by_id=AsyncMock(return_value=make_conversation()),
        touch=AsyncMock(),
    )

    messages = SimpleNamespace(create=AsyncMock())

    service, _, factory = build_service(
        answer_service=answer_service,
        conversations=conversations,
        messages=messages,
        clock_values=(
            2_000_000_000,
            1_000_000_000,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="duración negativa",
    ):
        await service.answer(
            user_id=7,
            conversation_id=10,
            query=generated.query,
        )

    assert factory.calls == 1

    messages.create.assert_not_awaited()
    conversations.touch.assert_not_awaited()
