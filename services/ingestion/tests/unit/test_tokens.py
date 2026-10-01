from datetime import UTC, datetime, timedelta

import jwt
import pytest

from catalina_ingestion.core.config import Settings
from catalina_ingestion.security.tokens import (
    TokenService,
    TokenValidationError,
)

SECRET = "catalina-test-secret-" + ("x" * 48)


def create_settings(
    **overrides,
) -> Settings:
    values = {
        "database_password": "database-test-password",
        "auth_jwt_secret": SECRET,
        "auth_jwt_algorithm": "HS256",
        "auth_access_token_minutes": 15,
        "auth_refresh_token_days": 7,
        "auth_jwt_issuer": "catalina-api",
        "auth_jwt_audience": "catalina-web",
    }

    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def test_create_and_decode_access_token():
    service = TokenService(create_settings())

    now = datetime.now(UTC).replace(
        microsecond=0
    )

    token = service.create_access_token(
        user_id=7,
        role="administrador",
        now=now,
    )

    claims = service.decode_access_token(token)

    assert claims.user_id == 7
    assert claims.role == "administrador"
    assert claims.token_id

    assert claims.issued_at == now

    assert claims.expires_at == (now + timedelta(minutes=15))


def test_access_token_contains_expected_claims():
    settings = create_settings()
    service = TokenService(settings)

    token = service.create_access_token(
        user_id=15,
        role="usuario",
    )

    payload = jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        issuer="catalina-api",
        audience="catalina-web",
    )

    assert payload["sub"] == "15"
    assert payload["role"] == "usuario"
    assert payload["type"] == "access"
    assert payload["jti"]
    assert payload["iss"] == "catalina-api"
    assert payload["aud"] == "catalina-web"


def test_decode_rejects_tampered_access_token():
    service = TokenService(create_settings())

    token = service.create_access_token(
        user_id=1,
        role="usuario",
    )

    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(TokenValidationError):
        service.decode_access_token(tampered)


def test_decode_rejects_token_with_wrong_secret():
    service = TokenService(create_settings())

    token = jwt.encode(
        {
            "sub": "1",
            "role": "usuario",
            "type": "access",
            "jti": "test-id",
            "iat": datetime.now(UTC),
            "exp": (datetime.now(UTC) + timedelta(minutes=15)),
            "iss": "catalina-api",
            "aud": "catalina-web",
        },
        "different-secret-" + ("z" * 40),
        algorithm="HS256",
    )

    with pytest.raises(TokenValidationError):
        service.decode_access_token(token)


def test_create_refresh_token_returns_hash_only_match():
    service = TokenService(create_settings())

    now = datetime(
        2026,
        9,
        30,
        20,
        0,
        tzinfo=UTC,
    )

    refresh = service.create_refresh_token(now=now)

    assert refresh.token
    assert refresh.token_hash
    assert refresh.token not in (refresh.token_hash)

    assert len(refresh.token_hash) == 64

    assert refresh.expires_at == (now + timedelta(days=7))

    assert service.verify_refresh_token(
        refresh.token,
        refresh.token_hash,
    )


def test_wrong_refresh_token_does_not_match():
    service = TokenService(create_settings())

    refresh = service.create_refresh_token()

    assert (
        service.verify_refresh_token(
            "otro-token",
            refresh.token_hash,
        )
        is False
    )


def test_refresh_tokens_are_unique():
    service = TokenService(create_settings())

    first = service.create_refresh_token()
    second = service.create_refresh_token()

    assert first.token != second.token
    assert first.token_hash != second.token_hash


def test_token_service_rejects_missing_secret():
    settings = create_settings(auth_jwt_secret=None)

    with pytest.raises(
        ValueError,
        match="AUTH_JWT_SECRET",
    ):
        TokenService(settings)


def test_create_access_token_rejects_invalid_user_id():
    service = TokenService(create_settings())

    with pytest.raises(
        ValueError,
        match="user_id",
    ):
        service.create_access_token(
            user_id=0,
            role="usuario",
        )


def test_create_access_token_rejects_blank_role():
    service = TokenService(create_settings())

    with pytest.raises(
        ValueError,
        match="rol",
    ):
        service.create_access_token(
            user_id=1,
            role="   ",
        )
