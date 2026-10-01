from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from catalina_ingestion.api.errors import (
    conversation_not_found_error_handler,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
)
from catalina_ingestion.schemas.conversations import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageListResponse,
    MessageResponse,
    UpdateConversationRequest,
)


def test_create_conversation_normalizes_title():
    payload = CreateConversationRequest(titulo="  Calendario académico  ")

    assert payload.titulo == "Calendario académico"


def test_create_conversation_uses_default_title():
    payload = CreateConversationRequest()

    assert payload.titulo == "Nueva conversación"


def test_create_conversation_rejects_blank_title():
    with pytest.raises(ValidationError):
        CreateConversationRequest(titulo="   ")


def test_update_conversation_normalizes_title():
    payload = UpdateConversationRequest(titulo="  Reglamento  ")

    assert payload.titulo == "Reglamento"


def test_update_conversation_rejects_blank_title():
    with pytest.raises(ValidationError):
        UpdateConversationRequest(titulo="   ")


def test_conversation_list_response():
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

    response = ConversationListResponse(
        items=[
            ConversationResponse(
                id=10,
                titulo="Consulta académica",
                fecha_inicio=started_at,
                fecha_actualizacion=updated_at,
            )
        ],
        limit=20,
        offset=0,
    )

    assert len(response.items) == 1
    assert response.items[0].id == 10
    assert response.limit == 20
    assert response.offset == 0


def test_message_list_response_preserves_decimal():
    created_at = datetime(
        2026,
        10,
        1,
        4,
        10,
        tzinfo=UTC,
    )

    response = MessageListResponse(
        items=[
            MessageResponse(
                id=20,
                conversacion_id=10,
                pregunta="Pregunta",
                respuesta="Respuesta",
                modelo="llama3.2:3b",
                tiempo_respuesta=Decimal("1.245"),
                fecha=created_at,
            )
        ],
        limit=50,
        offset=0,
    )

    assert response.items[0].tiempo_respuesta == Decimal("1.245")


@pytest.mark.asyncio
async def test_conversation_not_found_handler():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/conversations/10",
        "headers": [],
    }

    request = Request(scope)

    response = await conversation_not_found_error_handler(
        request,
        ConversationNotFoundError(),
    )

    assert response.status_code == 404

    assert response.headers["x-request-id"]

    assert "www-authenticate" not in response.headers

    body = response.body.decode("utf-8")

    assert "CONVERSATION_NOT_FOUND" in body

    assert "Conversación no encontrada." in body

    assert '"retryable":false' in body
