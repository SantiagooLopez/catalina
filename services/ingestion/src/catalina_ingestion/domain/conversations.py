from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Conversation:
    id: int
    usuario_id: int
    titulo: str
    fecha_inicio: datetime
    fecha_actualizacion: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: int
    conversacion_id: int
    pregunta: str
    respuesta: str
    modelo: str | None
    tiempo_respuesta: Decimal | None
    fecha: datetime
