from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import (
    create_app,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.conversation_answers import (
    ConversationAnswerResult,
)
from catalina_ingestion.domain.conversations import (
    Message,
)
from catalina_ingestion.domain.exceptions import (
    ConversationNotFoundError,
)
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
    GenerationStatistics,
)
from catalina_ingestion.domain.rag_context import (
    ContextSource,
)


def make_source() -> ContextSource:
    return ContextSource(
        citation_id="S1",
        point_id="point-1",
        document_id=11,
        document_version_id=11,
        document_name=("Modificación del Calendario Académico de Pregrado 2026"),
        version="050-2026",
        page_start=1,
        page_end=1,
        section=("Por el cual se modifica el Calendario Académico"),
        index_run_id="run-1",
    )


def make_message(
    *,
    question: str,
    answer: str,
    model: str | None,
) -> Message:
    return Message(
        id=20,
        conversacion_id=10,
        pregunta=question,
        respuesta=answer,
        modelo=model,
        tiempo_respuesta=Decimal("1.245"),
        fecha=datetime.now(UTC),
    )


def create_test_client(
    service,
) -> tuple[
    TestClient,
    SimpleNamespace,
]:
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

    app = create_app()

    app.state.auth_service = auth_service

    app.state.conversation_answer_service = service

    return (
        TestClient(app),
        auth_service,
    )


def auth_headers() -> dict[str, str]:
    return {"Authorization": ("Bearer access-token")}


def test_health_endpoint():
    app = create_app()

    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service": "catalina-ingestion",
    }


def test_answers_returns_document_identifier_resolution():
    source = make_source()

    answer = GeneratedAnswer(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        text=(
            "El acuerdo identificado en la "
            "fuente institucional principal "
            "corresponde al identificador "
            "documental 050-2026. [S1]"
        ),
        generated=False,
        reason=(GenerationReason.DOCUMENT_IDENTIFIER_RESOLVED),
        model=None,
        citations=(source,),
        statistics=None,
    )

    result = ConversationAnswerResult(
        answer=answer,
        message=make_message(
            question=answer.query,
            answer=answer.text,
            model=None,
        ),
    )

    service = SimpleNamespace(answer=AsyncMock(return_value=result))

    client, auth = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 10,
            "query": answer.query,
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["conversation_id"] == 10
    assert payload["message_id"] == 20
    assert payload["query"] == answer.query
    assert payload["generated"] is False

    assert payload["reason"] == "document_identifier_resolved"

    assert payload["model"] is None
    assert payload["statistics"] is None

    assert len(payload["citations"]) == 1

    assert payload["citations"][0]["citation_id"] == "S1"

    assert payload["citations"][0]["version"] == "050-2026"

    assert "050-2026" in payload["text"]

    (
        service.answer.assert_awaited_once_with(
            user_id=7,
            conversation_id=10,
            query=answer.query,
        )
    )

    (
        auth.get_current_user.assert_awaited_once_with(
            access_token="access-token",
        )
    )


def test_answers_returns_unsupported_grounding():
    query = "¿Dónde queda la sede de la Universidad Católica de Colombia en Cali?"

    answer = GeneratedAnswer(
        query=query,
        text=(
            "No encontré evidencia "
            "institucional suficiente para "
            "responder esta pregunta "
            "con seguridad."
        ),
        generated=False,
        reason=(GenerationReason.UNSUPPORTED_GROUNDING),
        model=None,
        citations=(),
        statistics=None,
    )

    result = ConversationAnswerResult(
        answer=answer,
        message=make_message(
            question=query,
            answer=answer.text,
            model=None,
        ),
    )

    service = SimpleNamespace(answer=AsyncMock(return_value=result))

    client, _ = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 10,
            "query": query,
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["conversation_id"] == 10
    assert payload["message_id"] == 20

    assert payload["generated"] is False

    assert payload["reason"] == "unsupported_grounding"

    assert payload["model"] is None
    assert payload["citations"] == []
    assert payload["statistics"] is None


def test_answers_rejects_blank_query_without_calling_service():
    service = SimpleNamespace(answer=AsyncMock())

    client, _ = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 10,
            "query": "   ",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 422

    service.answer.assert_not_awaited()


def test_general_chat_serializes_without_documentary_citations():
    answer = GeneratedAnswer(
        query="¿Cómo me llamo?", text="Te llamas Ana.", generated=True,
        reason=GenerationReason.GENERAL_CHAT, model="llama3.2:3b", citations=(),
        statistics=GenerationStatistics(1, 1, 1, 1, 1, 1),
    )
    result = ConversationAnswerResult(
        answer=answer,
        message=make_message(question=answer.query, answer=answer.text, model=answer.model),
    )
    service = SimpleNamespace(answer=AsyncMock(return_value=result))
    client, _ = create_test_client(service)
    response = client.post(
        "/api/v1/answers", headers=auth_headers(),
        json={"conversation_id": 10, "query": answer.query},
    )
    assert response.status_code == 200
    assert response.json()["reason"] == "general_chat"
    assert response.json()["citations"] == []
    assert response.json()["text"] == "Te llamas Ana."


def test_oversized_query_does_not_call_model():
    service = SimpleNamespace(answer=AsyncMock())
    client, _ = create_test_client(service)
    response = client.post(
        "/api/v1/answers", headers=auth_headers(),
        json={"conversation_id": 10, "query": "a" * 1001},
    )
    assert response.status_code == 422
    service.answer.assert_not_awaited()


def test_answers_rejects_invalid_conversation_id():
    service = SimpleNamespace(answer=AsyncMock())

    client, _ = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 0,
            "query": "Pregunta",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 422

    service.answer.assert_not_awaited()


def test_answers_requires_bearer():
    service = SimpleNamespace(answer=AsyncMock())

    client, auth = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 10,
            "query": "Pregunta",
        },
    )

    assert response.status_code == 401

    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"

    (auth.get_current_user.assert_not_awaited())

    service.answer.assert_not_awaited()


def test_answers_foreign_conversation_returns_404():
    service = SimpleNamespace(answer=AsyncMock(side_effect=(ConversationNotFoundError())))

    client, _ = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "conversation_id": 99,
            "query": "Pregunta",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 404

    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_openapi_contains_api_routes():
    app = create_app()

    schema = app.openapi()

    assert "/api/v1/health" in schema["paths"]

    assert "/api/v1/answers" in schema["paths"]

    assert "get" in schema["paths"]["/api/v1/health"]

    operation = schema["paths"]["/api/v1/answers"]["post"]

    assert operation["security"]
