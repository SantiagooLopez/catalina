from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import (
    create_app,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)
from catalina_ingestion.domain.exceptions import (
    GenerationError,
    TransientGenerationError,
)
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
)

QUERY = "¿Cuándo inicia el semestre?"
CONVERSATION_ID = 10


def create_client_for_error(
    error: Exception,
    *,
    raise_server_exceptions: bool = True,
):
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

    service = SimpleNamespace(answer=AsyncMock(side_effect=error))

    app = create_app()

    app.state.auth_service = auth_service

    app.state.conversation_answer_service = service

    client = TestClient(
        app,
        raise_server_exceptions=(raise_server_exceptions),
    )

    return client, service


def answer_request(
    client: TestClient,
):
    return client.post(
        "/api/v1/answers",
        json={
            "conversation_id": CONVERSATION_ID,
            "query": QUERY,
        },
        headers={"Authorization": "Bearer access-token"},
    )


def assert_error_contract(
    response,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    assert response.status_code == status_code

    payload = response.json()

    assert payload["error"]["code"] == code

    assert payload["error"]["message"] == message

    assert payload["error"]["retryable"] is retryable

    assert payload["error"]["request_id"]

    assert response.headers.get("x-request-id")


def test_retrieval_invalid_query_returns_400():
    error = RetrievalExecutionError(
        "INVALID_QUERY",
        ("La consulta no cumple los requisitos de entrada."),
        retryable=False,
        request_id="request-invalid",
    )

    client, service = create_client_for_error(error)

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=400,
        code="INVALID_QUERY",
        message=("La consulta no cumple los requisitos de entrada."),
        retryable=False,
    )

    service.answer.assert_awaited_once()


def test_retrieval_retryable_failure_returns_503():
    error = RetrievalExecutionError(
        "DATABASE_UNAVAILABLE",
        ("No fue posible consultar la base de datos."),
        retryable=True,
        request_id="request-database",
    )

    client, service = create_client_for_error(error)

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=503,
        code="DATABASE_UNAVAILABLE",
        message=("No fue posible consultar la base de datos."),
        retryable=True,
    )

    service.answer.assert_awaited_once()


def test_retrieval_timeout_returns_504():
    error = RetrievalExecutionError(
        "RETRIEVAL_TIMEOUT",
        ("La recuperación excedió el tiempo máximo permitido."),
        retryable=True,
        request_id="request-timeout",
    )

    client, service = create_client_for_error(error)

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=504,
        code="RETRIEVAL_TIMEOUT",
        message=("La recuperación excedió el tiempo máximo permitido."),
        retryable=True,
    )

    service.answer.assert_awaited_once()


def test_generation_validation_failure_returns_502():
    error = GenerationError(
        "GENERATION_VERIFICATION_FAILED",
        ("La respuesta generada no superó la validación factual."),
    )

    client, service = create_client_for_error(error)

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=502,
        code=("GENERATION_VERIFICATION_FAILED"),
        message=("La respuesta generada no superó la validación factual."),
        retryable=False,
    )

    service.answer.assert_awaited_once()


def test_transient_generation_failure_returns_503():
    error = TransientGenerationError(
        "OLLAMA_GENERATION_TEMPORARY_ERROR",
        ("Ollama no pudo completar temporalmente la generación."),
    )

    client, service = create_client_for_error(error)

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=503,
        code=("OLLAMA_GENERATION_TEMPORARY_ERROR"),
        message=("Ollama no pudo completar temporalmente la generación."),
        retryable=True,
    )

    service.answer.assert_awaited_once()


def test_unexpected_error_returns_safe_500():
    internal_message = "password=super-secret database crashed"

    client, service = create_client_for_error(
        RuntimeError(internal_message),
        raise_server_exceptions=False,
    )

    response = answer_request(client)

    assert_error_contract(
        response,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message=("Ocurrió un error interno procesando la solicitud."),
        retryable=False,
    )

    body = response.text

    assert internal_message not in body
    assert "super-secret" not in body

    service.answer.assert_awaited_once()
