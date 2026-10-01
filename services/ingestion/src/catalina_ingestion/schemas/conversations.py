from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CreateConversationRequest(BaseModel):
    titulo: str = Field(
        default="Nueva conversación",
        min_length=1,
        max_length=160,
    )

    @field_validator("titulo")
    @classmethod
    def normalize_title(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("titulo no puede estar vacío.")

        return normalized


class UpdateConversationRequest(BaseModel):
    titulo: str = Field(
        min_length=1,
        max_length=160,
    )

    @field_validator("titulo")
    @classmethod
    def normalize_title(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("titulo no puede estar vacío.")

        return normalized


class ConversationResponse(BaseModel):
    id: int
    titulo: str
    fecha_inicio: datetime
    fecha_actualizacion: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    limit: int
    offset: int


class MessageResponse(BaseModel):
    id: int
    conversacion_id: int
    pregunta: str
    respuesta: str
    modelo: str | None
    tiempo_respuesta: Decimal | None
    fecha: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    limit: int
    offset: int
