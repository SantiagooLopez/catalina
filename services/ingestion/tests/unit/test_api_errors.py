from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import create_app
from catalina_ingestion.domain.exceptions import (
    GenerationError,
    TransientGenerationError,
)
from catalina_ingestion.domain.retrieval_runtime import (
    RetrievalExecutionError,
)

QUERY = "¿Cuál es la información institucional?"


def create_client_for_error(
    error: Exception,
    *,
    raise_server_exceptions: bool = True,
) -> tuple[TestClient, AsyncMock]:
    service_answer = AsyncMock(side_effect=error)

    app = create_app()

    app.state.answer_service = SimpleNamespace(answer=service_answer)

    client = TestClient(
        app,
        raise_server_exceptions=raise_server_exceptions,
    )

    return client, service_answer


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

    assert set(payload) == {"error"}

    error = payload["error"]

    assert error["code"] == code
    assert error["message"] == message
    assert error["retryable"] is retryable

    assert isinstance(
        error["request_id"],
        str,
    )
    assert error["request_id"]

    assert response.headers["x-request-id"] == error["request_id"]


def test_retrieval_invalid_query_returns_400():
    error = RetrievalExecutionError(
        "INVALID_QUERY",
        "La consulta no cumple los requisitos de entrada.",
        retryable=False,
        request_id="request-invalid",
    )

    client, service_answer = create_client_for_error(error)

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=400,
        code="INVALID_QUERY",
        message=("La consulta no cumple los requisitos de entrada."),
        retryable=False,
    )

    assert response.json()["error"]["request_id"] == "request-invalid"

    service_answer.assert_awaited_once()


def test_retrieval_retryable_failure_returns_503():
    error = RetrievalExecutionError(
        "DATABASE_UNAVAILABLE",
        "No fue posible consultar la base de datos.",
        retryable=True,
        request_id="request-database",
    )

    client, _ = create_client_for_error(error)

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=503,
        code="DATABASE_UNAVAILABLE",
        message=("No fue posible consultar la base de datos."),
        retryable=True,
    )


def test_retrieval_timeout_returns_504():
    error = RetrievalExecutionError(
        "RETRIEVAL_TIMEOUT",
        "La recuperación excedió el tiempo máximo permitido.",
        retryable=True,
        request_id="request-timeout",
    )

    client, _ = create_client_for_error(error)

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=504,
        code="RETRIEVAL_TIMEOUT",
        message=("La recuperación excedió el tiempo máximo permitido."),
        retryable=True,
    )


def test_generation_validation_failure_returns_502():
    error = GenerationError(
        "GENERATION_VERIFICATION_FAILED",
        ("La respuesta generada no superó la validación factual."),
    )

    client, _ = create_client_for_error(error)

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=502,
        code="GENERATION_VERIFICATION_FAILED",
        message=("La respuesta generada no superó la validación factual."),
        retryable=False,
    )


def test_transient_generation_failure_returns_503():
    error = TransientGenerationError(
        "OLLAMA_GENERATION_TEMPORARY_ERROR",
        ("Ollama no pudo completar temporalmente la generación."),
    )

    client, _ = create_client_for_error(error)

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=503,
        code="OLLAMA_GENERATION_TEMPORARY_ERROR",
        message=("Ollama no pudo completar temporalmente la generación."),
        retryable=True,
    )


def test_unexpected_error_returns_safe_500():
    internal_message = "password=super-secret database crashed"

    client, _ = create_client_for_error(
        RuntimeError(internal_message),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/api/v1/answers",
        json={"query": QUERY},
    )

    assert_error_contract(
        response,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message=("Ocurrió un error interno procesando la solicitud."),
        retryable=False,
    )

    response_text = response.text

    assert internal_message not in response_text
    assert "super-secret" not in response_text
