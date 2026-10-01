import pytest
from pydantic import ValidationError
from starlette.requests import Request

from catalina_ingestion.api.errors import (
    authentication_error_handler,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from catalina_ingestion.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
)


def test_login_request_normalizes_email():
    payload = LoginRequest(
        email=" Usuario@UCATOLICA.EDU.CO ",
        password="secreto",
    )

    assert payload.email == "usuario@ucatolica.edu.co"


def test_login_request_rejects_invalid_email():
    with pytest.raises(
        ValidationError,
    ):
        LoginRequest(
            email="correo-invalido",
            password="secreto",
        )


def test_refresh_request_strips_token():
    payload = RefreshRequest(refresh_token=" token-seguro ")

    assert payload.refresh_token == "token-seguro"


def test_logout_request_rejects_blank_token():
    with pytest.raises(
        ValidationError,
    ):
        LogoutRequest(refresh_token="   ")


def create_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            InvalidCredentialsError(),
            "INVALID_CREDENTIALS",
        ),
        (
            InvalidRefreshTokenError(),
            "INVALID_REFRESH_TOKEN",
        ),
        (
            InvalidAccessTokenError(),
            "INVALID_ACCESS_TOKEN",
        ),
    ],
)
async def test_authentication_errors_return_401(
    error,
    expected_code,
):
    response = await authentication_error_handler(
        create_request(),
        error,
    )

    assert response.status_code == 401

    assert response.headers["WWW-Authenticate"] == "Bearer"

    assert response.headers["X-Request-ID"]

    body = response.body.decode("utf-8")

    assert expected_code in body
    assert '"retryable":false' in body
