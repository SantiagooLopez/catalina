from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from catalina_ingestion.api.app import (
    create_app,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
)


def client() -> TestClient:
    return TestClient(create_app())


def authenticated_client() -> TestClient:
    app = create_app()

    app.state.auth_service = SimpleNamespace(
        get_current_user=AsyncMock(
            return_value=AuthenticatedUser(
                id=1,
                email="admin@catalina.local",
                nombre="Administrador",
                rol="administrador",
                activo=True,
            )
        )
    )

    return TestClient(app)


def test_security_headers_are_present():
    response = client().get("/api/v1/health")

    assert response.status_code == 200

    assert response.headers["x-content-type-options"] == "nosniff"

    assert response.headers["x-frame-options"] == "DENY"

    assert response.headers["referrer-policy"] == "no-referrer"

    assert response.headers["cache-control"] == "no-store"

    assert response.headers.get("x-request-id")


def test_request_id_is_preserved():
    request_id = "catalina-test-request-id"

    response = client().get(
        "/api/v1/health",
        headers={"X-Request-ID": request_id},
    )

    assert response.headers["x-request-id"] == request_id


def test_protected_endpoint_requires_authentication():
    response = client().get("/api/v1/admin/ingestion-jobs/not-a-uuid")

    assert response.status_code == 401


def test_invalid_uuid_has_error_contract():
    response = authenticated_client().get(
        ("/api/v1/admin/ingestion-jobs/not-a-uuid"),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422

    payload = response.json()

    assert payload["error"]["code"] == "VALIDATION_ERROR"

    assert payload["error"]["retryable"] is False

    assert payload["error"]["request_id"]


def test_invalid_pagination_has_error_contract():
    response = authenticated_client().get(
        ("/api/v1/admin/ingestion-jobs?limit=999"),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422

    payload = response.json()

    assert payload["error"]["code"] == "VALIDATION_ERROR"

    assert payload["error"]["retryable"] is False


def test_openapi_still_contains_core_routes():
    schema = create_app().openapi()

    required = {
        "/api/v1/health",
        "/api/v1/answers",
        "/api/v1/admin/documents",
        "/api/v1/admin/ingestion-jobs",
        "/api/v1/admin/indexing-runs",
        "/api/v1/admin/metrics/summary",
        "/api/v1/admin/metrics/ingestion",
        "/api/v1/admin/metrics/rag",
    }

    missing = required - set(schema["paths"])

    assert not missing
