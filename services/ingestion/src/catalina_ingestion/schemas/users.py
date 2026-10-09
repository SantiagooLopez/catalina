from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class UpdateProfileRequest(BaseModel):
    nombre: str = Field(
        min_length=1,
        max_length=160,
    )

    @field_validator("nombre")
    @classmethod
    def normalize_name(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("El nombre no puede estar vacío.")

        return cleaned


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
    )

    new_password: str = Field(
        min_length=8,
        max_length=256,
    )


class UpdateUserStatusRequest(BaseModel):
    activo: bool


class UpdateUserRoleRequest(BaseModel):
    rol: str

    @field_validator("rol")
    @classmethod
    def normalize_role(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip().lower()

        if cleaned not in {
            "usuario",
            "administrador",
        }:
            raise ValueError("Rol no soportado.")

        return cleaned


class UserResponse(BaseModel):
    id: int
    email: str
    nombre: str
    rol: str
    activo: bool
    fecha_creacion: datetime | None
    fecha_actualizacion: datetime
    ultimo_acceso: datetime | None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    limit: int
    offset: int
