from decimal import Decimal, InvalidOperation
from typing import Any

from catalina_ingestion.domain.conversations import (
    Message,
)

_MESSAGE_COLUMNS = """
    m.id,
    m.conversacion_id,
    m.pregunta,
    m.respuesta,
    m.modelo,
    m.tiempo_respuesta,
    m.fecha
"""


class MessageRepository:
    async def create(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
        pregunta: str,
        respuesta: str,
        modelo: str | None = None,
        tiempo_respuesta: Decimal | int | float | None = None,
    ) -> Message | None:
        normalized_conversation_id = _validate_positive_id(
            "conversation_id",
            conversation_id,
        )

        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        normalized_question = _normalize_required_text(
            "pregunta",
            pregunta,
        )

        normalized_answer = _normalize_required_text(
            "respuesta",
            respuesta,
        )

        normalized_model = _normalize_optional_text(modelo)

        normalized_response_time = _normalize_response_time(tiempo_respuesta)

        result = await connection.execute(
            """
            INSERT INTO catalina.mensajes (
                conversacion_id,
                pregunta,
                respuesta,
                modelo,
                tiempo_respuesta
            )
            SELECT
                c.id,
                %s,
                %s,
                %s,
                %s
            FROM catalina.conversaciones c
            WHERE c.id = %s
              AND c.usuario_id = %s
            RETURNING
                id,
                conversacion_id,
                pregunta,
                respuesta,
                modelo,
                tiempo_respuesta,
                fecha
            """,
            (
                normalized_question,
                normalized_answer,
                normalized_model,
                normalized_response_time,
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        if row is None:
            return None

        return _to_message(row)

    async def get_by_id(
        self,
        connection: Any,
        *,
        message_id: int,
        conversation_id: int,
        usuario_id: int,
    ) -> Message | None:
        normalized_message_id = _validate_positive_id(
            "message_id",
            message_id,
        )

        normalized_conversation_id = _validate_positive_id(
            "conversation_id",
            conversation_id,
        )

        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        result = await connection.execute(
            f"""
            SELECT
                {_MESSAGE_COLUMNS}
            FROM catalina.mensajes m
            JOIN catalina.conversaciones c
              ON c.id = m.conversacion_id
            WHERE m.id = %s
              AND m.conversacion_id = %s
              AND c.usuario_id = %s
            """,
            (
                normalized_message_id,
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        if row is None:
            return None

        return _to_message(row)

    async def list_by_conversation(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        normalized_conversation_id = _validate_positive_id(
            "conversation_id",
            conversation_id,
        )

        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        normalized_limit = _validate_limit(limit)

        normalized_offset = _validate_offset(offset)

        result = await connection.execute(
            f"""
            SELECT
                {_MESSAGE_COLUMNS}
            FROM catalina.mensajes m
            JOIN catalina.conversaciones c
              ON c.id = m.conversacion_id
            WHERE m.conversacion_id = %s
              AND c.usuario_id = %s
            ORDER BY
                m.fecha ASC,
                m.id ASC
            LIMIT %s
            OFFSET %s
            """,
            (
                normalized_conversation_id,
                normalized_user_id,
                normalized_limit,
                normalized_offset,
            ),
        )

        rows = await result.fetchall()

        return [_to_message(row) for row in rows]


def _normalize_required_text(
    name: str,
    value: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} debe ser una cadena de texto.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{name} no puede estar vacío.")

    return normalized


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("modelo debe ser una cadena de texto.")

    normalized = value.strip()

    if not normalized:
        return None

    return normalized


def _normalize_response_time(
    value: Decimal | int | float | None,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("tiempo_respuesta debe ser numérico.")

    try:
        normalized = Decimal(str(value))
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ) as error:
        raise ValueError("tiempo_respuesta debe ser numérico.") from error

    if not normalized.is_finite():
        raise ValueError("tiempo_respuesta debe ser finito.")

    if normalized < 0:
        raise ValueError("tiempo_respuesta no puede ser negativo.")

    return normalized


def _validate_positive_id(
    name: str,
    value: int,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} debe ser un entero positivo.")

    return value


def _validate_limit(
    limit: int,
) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100.")

    return limit


def _validate_offset(
    offset: int,
) -> int:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset debe ser un entero mayor o igual a cero.")

    return offset


def _to_message(
    row: Any,
) -> Message:
    return Message(
        id=row[0],
        conversacion_id=row[1],
        pregunta=row[2],
        respuesta=row[3],
        modelo=row[4],
        tiempo_respuesta=row[5],
        fecha=row[6],
    )
