from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import create_app
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
    GenerationReason,
)
from catalina_ingestion.domain.rag_context import ContextSource


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


def create_test_client(
    service,
) -> TestClient:
    app = create_app()
    app.state.answer_service = service
    return TestClient(app)


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

    result = GeneratedAnswer(
        query=("¿Qué acuerdo modificó el calendario académico de pregrado de 2026?"),
        text=(
            "El acuerdo identificado en la fuente "
            "institucional principal corresponde al "
            "identificador documental 050-2026. [S1]"
        ),
        generated=False,
        reason=(GenerationReason.DOCUMENT_IDENTIFIER_RESOLVED),
        model=None,
        citations=(source,),
        statistics=None,
    )

    service = SimpleNamespace(answer=AsyncMock(return_value=result))

    client = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "query": result.query,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["query"] == result.query
    assert payload["generated"] is False

    assert payload["reason"] == "document_identifier_resolved"

    assert payload["model"] is None
    assert payload["statistics"] is None

    assert len(payload["citations"]) == 1

    assert payload["citations"][0]["citation_id"] == "S1"

    assert payload["citations"][0]["version"] == "050-2026"

    assert "050-2026" in payload["text"]

    service.answer.assert_awaited_once()


def test_answers_returns_unsupported_grounding():
    query = "¿Dónde queda la sede de la Universidad Católica de Colombia en Cali?"

    result = GeneratedAnswer(
        query=query,
        text=(
            "No encontré evidencia institucional "
            "suficiente para responder esta pregunta "
            "con seguridad."
        ),
        generated=False,
        reason=GenerationReason.UNSUPPORTED_GROUNDING,
        model=None,
        citations=(),
        statistics=None,
    )

    service = SimpleNamespace(answer=AsyncMock(return_value=result))

    client = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "query": query,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["generated"] is False

    assert payload["reason"] == "unsupported_grounding"

    assert payload["model"] is None
    assert payload["citations"] == []
    assert payload["statistics"] is None


def test_answers_rejects_blank_query_without_calling_service():
    service = SimpleNamespace(answer=AsyncMock())

    client = create_test_client(service)

    response = client.post(
        "/api/v1/answers",
        json={
            "query": "   ",
        },
    )

    assert response.status_code == 422

    service.answer.assert_not_awaited()


def test_openapi_contains_api_routes():
    app = create_app()

    schema = app.openapi()

    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/answers" in schema["paths"]

    assert "get" in schema["paths"]["/api/v1/health"]

    assert "post" in schema["paths"]["/api/v1/answers"]
