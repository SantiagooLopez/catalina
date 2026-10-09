from datetime import datetime
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


class DocumentResponse(BaseModel):
    id: int
    nombre: str
    tipo_archivo: str | None
    categoria: str | None
    descripcion: str | None
    estado: str | None
    fecha_carga: datetime | None
    codigo: str | None
    idioma: str
    origen: str | None
    metadatos: dict[str, Any]
    fecha_actualizacion: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    limit: int
    offset: int


class DocumentVersionResponse(BaseModel):
    id: int
    documento_id: int | None
    version: str
    nombre_archivo_original: str | None
    extension: str | None
    mime_type: str | None
    tamano_bytes: int | None
    hash_contenido: str | None
    estado: str
    total_paginas: int | None
    total_secciones: int | None
    total_chunks: int | None
    modelo_embedding: str | None
    dimension_embedding: int | None
    fecha_indexacion: datetime | None
    fecha_actualizacion: datetime
    error_codigo: str | None
    error_detalle: str | None


class DocumentVersionListResponse(BaseModel):
    items: list[DocumentVersionResponse]
    limit: int
    offset: int


class DocumentStatusRequest(BaseModel):
    estado: str

    @field_validator("estado")
    @classmethod
    def validate_status(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip().lower()

        if cleaned not in {
            "activo",
            "inactivo",
        }:
            raise ValueError("El estado debe ser activo o inactivo.")

        return cleaned


class DocumentRegistrationResponse(BaseModel):
    document_id: int
    document_version_id: int
    ingestion_job_id: UUID
    codigo: str
    version: str
    estado: str
    sha256: str
