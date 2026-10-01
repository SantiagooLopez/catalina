from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalina_ingestion.api.errors import (
    authentication_error_handler,
)
from catalina_ingestion.api.routes.auth import (
    router,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
    AuthenticationResult,
    TokenRefreshResult,
)
from catalina_ingestion.domain.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
)


def create_test_app(
    service,
) -> FastAPI:
    app = FastAPI()

    app.state.auth_service = service

    app.include_router(
        router,
        prefix="/api/v1",
    )

    app.add_exception_handler(
        AuthenticationError,
        authentication_error_handler,
    )

    return app


def test_login_returns_tokens_and_user():
    expires_at = datetime.now(UTC) + timedelta(days=7)

    service = SimpleNamespace(
        authenticate=AsyncMock(
            return_value=AuthenticationResult(
                user_id=7,
                email="usuario@ucatolica.edu.co",
                nombre="Usuario Catalina",
                rol="usuario",
                access_token="access-token",
                refresh_token="refresh-token",
                refresh_expires_at=expires_at,
            )
        )
    )

    client = TestClient(create_test_app(service))

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": (" Usuario@UCATOLICA.EDU.CO "),
            "password": "secreto",
        },
        headers={
            "User-Agent": "pytest-agent",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["access_token"] == "access-token"

    assert payload["token_type"] == "bearer"

    assert payload["refresh_token"] == "refresh-token"

    assert payload["user"] == {
        "id": 7,
        "email": "usuario@ucatolica.edu.co",
        "nombre": "Usuario Catalina",
        "rol": "usuario",
        "activo": True,
    }

    service.authenticate.assert_awaited_once()

    kwargs = service.authenticate.await_args.kwargs

    assert kwargs["email"] == "usuario@ucatolica.edu.co"

    assert kwargs["password"] == "secreto"
    assert kwargs["user_agent"] == "pytest-agent"


def test_login_invalid_credentials_returns_401():
    service = SimpleNamespace(authenticate=AsyncMock(side_effect=InvalidCredentialsError()))

    client = TestClient(create_test_app(service))

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "usuario@ucatolica.edu.co",
            "password": "incorrecta",
        },
    )

    assert response.status_code == 401

    assert response.headers["www-authenticate"] == "Bearer"

    payload = response.json()

    assert payload["error"]["code"] == "INVALID_CREDENTIALS"


def test_refresh_returns_rotated_tokens():
    expires_at = datetime.now(UTC) + timedelta(days=7)

    service = SimpleNamespace(
        refresh=AsyncMock(
            return_value=TokenRefreshResult(
                user_id=7,
                access_token="new-access-token",
                refresh_token="new-refresh-token",
                refresh_expires_at=expires_at,
            )
        )
    )

    client = TestClient(create_test_app(service))

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "old-refresh-token",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["access_token"] == "new-access-token"

    assert payload["refresh_token"] == "new-refresh-token"

    assert payload["token_type"] == "bearer"

    service.refresh.assert_awaited_once_with(
        refresh_token="old-refresh-token",
    )


def test_logout_returns_204():
    service = SimpleNamespace(logout=AsyncMock(return_value=True))

    client = TestClient(create_test_app(service))

    response = client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": "refresh-token",
        },
    )

    assert response.status_code == 204
    assert response.content == b""

    service.logout.assert_awaited_once_with(
        refresh_token="refresh-token",
    )


def test_me_returns_authenticated_user():
    service = SimpleNamespace(
        get_current_user=AsyncMock(
            return_value=AuthenticatedUser(
                id=7,
                email="usuario@ucatolica.edu.co",
                nombre="Usuario Catalina",
                rol="usuario",
                activo=True,
            )
        )
    )

    client = TestClient(create_test_app(service))

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": ("Bearer access-token")},
    )

    assert response.status_code == 200

    assert response.json() == {
        "id": 7,
        "email": "usuario@ucatolica.edu.co",
        "nombre": "Usuario Catalina",
        "rol": "usuario",
        "activo": True,
    }

    (
        service.get_current_user.assert_awaited_once_with(
            access_token="access-token",
        )
    )


def test_me_without_bearer_returns_401():
    service = SimpleNamespace(get_current_user=AsyncMock())

    client = TestClient(create_test_app(service))

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401

    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"

    (service.get_current_user.assert_not_awaited())


def test_auth_openapi_exposes_bearer_security():
    service = SimpleNamespace()

    app = create_test_app(service)

    schema = app.openapi()

    paths = schema["paths"]

    assert "/api/v1/auth/login" in paths

    assert "/api/v1/auth/refresh" in paths

    assert "/api/v1/auth/logout" in paths

    assert "/api/v1/auth/me" in paths

    security = paths["/api/v1/auth/me"]["get"]["security"]

    assert security
