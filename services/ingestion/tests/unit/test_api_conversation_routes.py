from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalina_ingestion.api.errors import (
    authentication_error_handler,
    conversation_not_found_error_handler,
)
from catalina_ingestion.api.routes.conversations import (
    router,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.conversations import (
    Conversation,
    Message,
)
from catalina_ingestion.domain.exceptions import (
    AuthenticationError,
    ConversationNotFoundError,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError as MissingConversation,
)


def conversation(
    *,
    conversation_id: int = 10,
    title: str = "Consulta académica",
) -> Conversation:
    started = datetime(
        2026,
        10,
        1,
        4,
        0,
        tzinfo=UTC,
    )

    updated = datetime(
        2026,
        10,
        1,
        4,
        5,
        tzinfo=UTC,
    )

    return Conversation(
        id=conversation_id,
        usuario_id=7,
        titulo=title,
        fecha_inicio=started,
        fecha_actualizacion=updated,
    )


def message() -> Message:
    return Message(
        id=20,
        conversacion_id=10,
        pregunta="Pregunta",
        respuesta="Respuesta",
        modelo="llama3.2:3b",
        tiempo_respuesta=Decimal("1.245"),
        fecha=datetime.now(UTC),
    )


def create_test_app(
    conversation_service,
) -> tuple[FastAPI, SimpleNamespace]:
    auth_service = SimpleNamespace(
        get_current_user=AsyncMock(
            return_value=AuthenticatedUser(
                id=7,
                email="usuario@catalina.local",
                nombre="Usuario Catalina",
                rol="usuario",
                activo=True,
            )
        )
    )

    app = FastAPI()

    app.state.auth_service = auth_service
    app.state.conversation_service = conversation_service

    app.include_router(
        router,
        prefix="/api/v1",
    )

    app.add_exception_handler(
        AuthenticationError,
        authentication_error_handler,
    )

    app.add_exception_handler(
        ConversationNotFoundError,
        conversation_not_found_error_handler,
    )

    return app, auth_service


def auth_headers() -> dict[str, str]:
    return {"Authorization": ("Bearer access-token")}


def test_create_conversation():
    service = SimpleNamespace(create_conversation=AsyncMock(return_value=conversation()))

    app, auth = create_test_app(service)

    client = TestClient(app)

    response = client.post(
        "/api/v1/conversations",
        json={"titulo": "Consulta académica"},
        headers=auth_headers(),
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["id"] == 10

    assert payload["titulo"] == "Consulta académica"

    (
        service.create_conversation.assert_awaited_once_with(
            user_id=7,
            title="Consulta académica",
        )
    )

    (
        auth.get_current_user.assert_awaited_once_with(
            access_token="access-token",
        )
    )


def test_list_conversations():
    service = SimpleNamespace(
        list_conversations=AsyncMock(
            return_value=[
                conversation(
                    conversation_id=11,
                    title="Segunda",
                ),
                conversation(
                    conversation_id=10,
                    title="Primera",
                ),
            ]
        )
    )

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.get(
        ("/api/v1/conversations?limit=25&offset=50"),
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["items"]) == 2
    assert payload["limit"] == 25
    assert payload["offset"] == 50

    (
        service.list_conversations.assert_awaited_once_with(
            user_id=7,
            limit=25,
            offset=50,
        )
    )


def test_get_conversation():
    service = SimpleNamespace(get_conversation=AsyncMock(return_value=conversation()))

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.get(
        "/api/v1/conversations/10",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["id"] == 10

    (
        service.get_conversation.assert_awaited_once_with(
            user_id=7,
            conversation_id=10,
        )
    )


def test_update_conversation():
    service = SimpleNamespace(
        update_title=AsyncMock(return_value=conversation(title="Nuevo título"))
    )

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.patch(
        "/api/v1/conversations/10",
        json={"titulo": "  Nuevo título  "},
        headers=auth_headers(),
    )

    assert response.status_code == 200

    assert response.json()["titulo"] == "Nuevo título"

    (
        service.update_title.assert_awaited_once_with(
            user_id=7,
            conversation_id=10,
            title="Nuevo título",
        )
    )


def test_delete_conversation():
    service = SimpleNamespace(delete_conversation=AsyncMock(return_value=None))

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.delete(
        "/api/v1/conversations/10",
        headers=auth_headers(),
    )

    assert response.status_code == 204
    assert response.content == b""

    (
        service.delete_conversation.assert_awaited_once_with(
            user_id=7,
            conversation_id=10,
        )
    )


def test_list_messages():
    service = SimpleNamespace(list_messages=AsyncMock(return_value=[message()]))

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.get(
        ("/api/v1/conversations/10/messages?limit=25&offset=5"),
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == 20
    assert payload["limit"] == 25
    assert payload["offset"] == 5

    (
        service.list_messages.assert_awaited_once_with(
            user_id=7,
            conversation_id=10,
            limit=25,
            offset=5,
        )
    )


def test_missing_bearer_returns_401():
    service = SimpleNamespace(list_conversations=AsyncMock())

    app, auth = create_test_app(service)

    client = TestClient(app)

    response = client.get("/api/v1/conversations")

    assert response.status_code == 401

    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"

    (auth.get_current_user.assert_not_awaited())

    (service.list_conversations.assert_not_awaited())


def test_missing_conversation_returns_404():
    service = SimpleNamespace(get_conversation=AsyncMock(side_effect=(MissingConversation())))

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.get(
        "/api/v1/conversations/999",
        headers=auth_headers(),
    )

    assert response.status_code == 404

    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_invalid_pagination_returns_422():
    service = SimpleNamespace(list_conversations=AsyncMock())

    app, _ = create_test_app(service)

    client = TestClient(app)

    response = client.get(
        ("/api/v1/conversations?limit=0&offset=-1"),
        headers=auth_headers(),
    )

    assert response.status_code == 422

    (service.list_conversations.assert_not_awaited())


def test_openapi_exposes_bearer_security():
    service = SimpleNamespace()

    app, _ = create_test_app(service)

    schema = app.openapi()

    operation = schema["paths"]["/api/v1/conversations"]["get"]

    assert operation["security"]
