from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
    )
    password: str = Field(
        min_length=1,
        max_length=4096,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
            or " " in normalized
        ):
            raise ValueError("El correo electrónico no es válido.")

        return normalized


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        max_length=2048,
    )

    @field_validator("refresh_token")
    @classmethod
    def normalize_refresh_token(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("El refresh token no puede estar vacío.")

        return normalized


class LogoutRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        max_length=2048,
    )

    @field_validator("refresh_token")
    @classmethod
    def normalize_refresh_token(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("El refresh token no puede estar vacío.")

        return normalized


class AuthUserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    rol: str
    activo: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    refresh_expires_at: datetime
    user: AuthUserResponse


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    refresh_expires_at: datetime


class MeResponse(AuthUserResponse):
    pass
