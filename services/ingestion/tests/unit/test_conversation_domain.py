from datetime import UTC, datetime
from decimal import Decimal

from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)


def test_conversation_domain():
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

    conversation = Conversation(
        id=10,
        usuario_id=7,
        titulo="Consulta calendario académico",
        fecha_inicio=started_at,
        fecha_actualizacion=updated_at,
    )

    assert conversation.id == 10
    assert conversation.usuario_id == 7

    assert conversation.titulo == "Consulta calendario académico"

    assert conversation.fecha_inicio == started_at

    assert conversation.fecha_actualizacion == updated_at


def test_message_domain():
    created_at = datetime(
        2026,
        10,
        1,
        3,
        10,
        tzinfo=UTC,
    )

    message = Message(
        id=15,
        conversacion_id=10,
        pregunta=("¿Cuál es el calendario académico?"),
        respuesta=("El calendario se encuentra definido en el documento institucional."),
        modelo="llama3.2:3b",
        tiempo_respuesta=Decimal("1.245"),
        fecha=created_at,
    )

    assert message.id == 15
    assert message.conversacion_id == 10

    assert message.modelo == "llama3.2:3b"

    assert message.tiempo_respuesta == Decimal("1.245")

    assert message.fecha == created_at


def test_message_allows_optional_generation_metadata():
    message = Message(
        id=16,
        conversacion_id=10,
        pregunta="Pregunta de prueba",
        respuesta="Respuesta de prueba",
        modelo=None,
        tiempo_respuesta=None,
        fecha=datetime.now(UTC),
    )

    assert message.modelo is None
    assert message.tiempo_respuesta is None
