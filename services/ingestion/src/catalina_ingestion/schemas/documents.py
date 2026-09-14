from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentRegistrationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    nombre: str = Field(min_length=3, max_length=255)
    categoria: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
    )
    version: str = Field(min_length=1, max_length=20)
    descripcion: str | None = Field(default=None, max_length=5000)
    idioma: str = Field(default="es", min_length=2, max_length=10)
    origen: str | None = Field(default=None, max_length=2000)
    metadatos: dict[str, Any] = Field(default_factory=dict)

    @field_validator("codigo", "categoria")
    @classmethod
    def normalize_lowercase(cls, value: str) -> str:
        return value.lower()

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")

        if any(character not in allowed for character in value):
            raise ValueError(
                "La versión solo puede contener letras, números, punto, guion o guion bajo."
            )

        return value


class DocumentRegistrationResult(BaseModel):
    document_id: int
    document_version_id: int
    ingestion_job_id: UUID
    codigo: str
    version: str
    estado: str
    sha256: str
    storage_path: str
