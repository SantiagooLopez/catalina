from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from catalina_ingestion.core.config import (
    Settings,
    get_settings,
)


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: int
    role: str
    token_id: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshToken:
    token: str
    token_hash: str
    expires_at: datetime


class TokenValidationError(ValueError):
    """Token de autenticación inválido."""


class TokenService:
    def __init__(
        self,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()

        secret = self.settings.auth_jwt_secret

        if secret is None or len(secret) < 32:
            raise ValueError("AUTH_JWT_SECRET debe estar configurado con al menos 32 caracteres.")

        self._secret = secret

    def create_access_token(
        self,
        *,
        user_id: int,
        role: str,
        now: datetime | None = None,
    ) -> str:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

        normalized_role = role.strip()

        if not normalized_role:
            raise ValueError("El rol no puede estar vacío.")

        issued_at = self._normalize_now(now)

        expires_at = issued_at + timedelta(minutes=(self.settings.auth_access_token_minutes))

        payload = {
            "sub": str(user_id),
            "role": normalized_role,
            "type": "access",
            "jti": str(uuid4()),
            "iat": issued_at,
            "exp": expires_at,
            "iss": self.settings.auth_jwt_issuer,
            "aud": self.settings.auth_jwt_audience,
        }

        return jwt.encode(
            payload,
            self._secret,
            algorithm=self.settings.auth_jwt_algorithm,
        )

    def decode_access_token(
        self,
        token: str,
    ) -> AccessTokenClaims:
        if not token:
            raise TokenValidationError("El access token está vacío.")

        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self.settings.auth_jwt_algorithm],
                issuer=self.settings.auth_jwt_issuer,
                audience=self.settings.auth_jwt_audience,
                options={
                    "require": [
                        "sub",
                        "role",
                        "type",
                        "jti",
                        "iat",
                        "exp",
                        "iss",
                        "aud",
                    ]
                },
            )

        except InvalidTokenError as error:
            raise TokenValidationError("El access token no es válido.") from error

        if payload.get("type") != "access":
            raise TokenValidationError("El token no es un access token.")

        try:
            user_id = int(payload["sub"])
            issued_at = datetime.fromtimestamp(
                payload["iat"],
                tz=UTC,
            )
            expires_at = datetime.fromtimestamp(
                payload["exp"],
                tz=UTC,
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            raise TokenValidationError("El access token contiene claims inválidos.") from error

        role = payload.get("role")
        token_id = payload.get("jti")

        if (
            user_id < 1
            or not isinstance(role, str)
            or not role.strip()
            or not isinstance(token_id, str)
            or not token_id.strip()
        ):
            raise TokenValidationError("El access token contiene claims inválidos.")

        return AccessTokenClaims(
            user_id=user_id,
            role=role,
            token_id=token_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )

    def create_refresh_token(
        self,
        *,
        now: datetime | None = None,
    ) -> RefreshToken:
        issued_at = self._normalize_now(now)

        token = token_urlsafe(48)

        return RefreshToken(
            token=token,
            token_hash=self.hash_refresh_token(token),
            expires_at=(issued_at + timedelta(days=(self.settings.auth_refresh_token_days))),
        )

    @staticmethod
    def hash_refresh_token(
        token: str,
    ) -> str:
        if not token:
            raise ValueError("El refresh token no puede estar vacío.")

        return sha256(token.encode("utf-8")).hexdigest()

    def verify_refresh_token(
        self,
        token: str,
        expected_hash: str,
    ) -> bool:
        if not token or not expected_hash:
            return False

        actual_hash = self.hash_refresh_token(token)

        return compare_digest(
            actual_hash,
            expected_hash,
        )

    @staticmethod
    def _normalize_now(
        value: datetime | None,
    ) -> datetime:
        current = value or datetime.now(UTC)

        if current.tzinfo is None:
            raise ValueError("La fecha debe incluir zona horaria.")

        return current.astimezone(UTC)
