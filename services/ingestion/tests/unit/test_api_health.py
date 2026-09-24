from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from catalina_ingestion.api.app import create_app
from catalina_ingestion.api.routes.health import (
    get_health_service,
)
from catalina_ingestion.services.health import (
    ReadinessResult,
)


def create_health_client(
    result: ReadinessResult,
) -> tuple[TestClient, AsyncMock]:
    check_readiness = AsyncMock(return_value=result)

    service = SimpleNamespace(check_readiness=check_readiness)

    app = create_app()

    def override_health_service():
        return service

    app.dependency_overrides[get_health_service] = override_health_service

    return (
        TestClient(app),
        check_readiness,
    )


def test_health_returns_200():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service": "catalina-ingestion",
    }


def test_readiness_returns_200_when_all_dependencies_are_ready():
    client, check_readiness = create_health_client(
        ReadinessResult(
            postgres=True,
            qdrant=True,
            ollama=True,
        )
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready",
        "service": "catalina-ingestion",
        "dependencies": {
            "postgres": "ok",
            "qdrant": "ok",
            "ollama": "ok",
        },
    }

    check_readiness.assert_awaited_once_with()


@pytest.mark.parametrize(
    (
        "postgres",
        "qdrant",
        "ollama",
        "failed_dependency",
    ),
    [
        (
            False,
            True,
            True,
            "postgres",
        ),
        (
            True,
            False,
            True,
            "qdrant",
        ),
        (
            True,
            True,
            False,
            "ollama",
        ),
    ],
)
def test_readiness_returns_503_when_dependency_is_unavailable(
    postgres: bool,
    qdrant: bool,
    ollama: bool,
    failed_dependency: str,
):
    client, check_readiness = create_health_client(
        ReadinessResult(
            postgres=postgres,
            qdrant=qdrant,
            ollama=ollama,
        )
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503

    payload = response.json()

    assert payload["status"] == "not_ready"
    assert payload["service"] == ("catalina-ingestion")

    assert payload["dependencies"][failed_dependency] == "error"

    for dependency, state in payload["dependencies"].items():
        if dependency != failed_dependency:
            assert state == "ok"

    check_readiness.assert_awaited_once_with()
