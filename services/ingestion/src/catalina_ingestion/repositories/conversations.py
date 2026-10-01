from typing import Any

from catalina_ingestion.domain.conversations import (
    Conversation,
)

DEFAULT_CONVERSATION_TITLE = "Nueva conversación"
MAX_CONVERSATION_TITLE_LENGTH = 160

_CONVERSATION_COLUMNS = """
    id,
    usuario_id,
    titulo,
    fecha_inicio,
    fecha_actualizacion
"""


class ConversationRepository:
    async def create(
        self,
        connection: Any,
        *,
        usuario_id: int,
        titulo: str = DEFAULT_CONVERSATION_TITLE,
    ) -> Conversation:
        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        normalized_title = _normalize_title(titulo)

        result = await connection.execute(
            f"""
            INSERT INTO catalina.conversaciones (
                usuario_id,
                titulo
            )
            VALUES (
                %s,
                %s
            )
            RETURNING
                {_CONVERSATION_COLUMNS}
            """,
            (
                normalized_user_id,
                normalized_title,
            ),
        )

        row = await result.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear la conversación.")

        return _to_conversation(row)

    async def get_by_id(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
    ) -> Conversation | None:
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
                {_CONVERSATION_COLUMNS}
            FROM catalina.conversaciones
            WHERE id = %s
              AND usuario_id = %s
            """,
            (
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        if row is None:
            return None

        return _to_conversation(row)

    async def update_title(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
        titulo: str,
    ) -> Conversation | None:
        normalized_conversation_id = _validate_positive_id(
            "conversation_id",
            conversation_id,
        )

        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        normalized_title = _normalize_title(titulo)

        result = await connection.execute(
            f"""
            UPDATE catalina.conversaciones
            SET
                titulo = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
              AND usuario_id = %s
            RETURNING
                {_CONVERSATION_COLUMNS}
            """,
            (
                normalized_title,
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        if row is None:
            return None

        return _to_conversation(row)

    async def touch(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
    ) -> Conversation | None:
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
            UPDATE catalina.conversaciones
            SET
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
              AND usuario_id = %s
            RETURNING
                {_CONVERSATION_COLUMNS}
            """,
            (
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        if row is None:
            return None

        return _to_conversation(row)

    async def delete(
        self,
        connection: Any,
        *,
        conversation_id: int,
        usuario_id: int,
    ) -> bool:
        normalized_conversation_id = _validate_positive_id(
            "conversation_id",
            conversation_id,
        )

        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        result = await connection.execute(
            """
            DELETE FROM catalina.conversaciones
            WHERE id = %s
              AND usuario_id = %s
            RETURNING id
            """,
            (
                normalized_conversation_id,
                normalized_user_id,
            ),
        )

        row = await result.fetchone()

        return row is not None

    async def list_by_user(
        self,
        connection: Any,
        *,
        usuario_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        normalized_user_id = _validate_positive_id(
            "usuario_id",
            usuario_id,
        )

        normalized_limit = _validate_limit(limit)

        normalized_offset = _validate_offset(offset)

        result = await connection.execute(
            f"""
            SELECT
                {_CONVERSATION_COLUMNS}
            FROM catalina.conversaciones
            WHERE usuario_id = %s
            ORDER BY
                fecha_actualizacion DESC,
                id DESC
            LIMIT %s
            OFFSET %s
            """,
            (
                normalized_user_id,
                normalized_limit,
                normalized_offset,
            ),
        )

        rows = await result.fetchall()

        return [_to_conversation(row) for row in rows]


def _normalize_title(
    title: str,
) -> str:
    if not isinstance(title, str):
        raise ValueError("titulo debe ser una cadena de texto.")

    normalized = title.strip()

    if not normalized:
        raise ValueError("titulo no puede estar vacío.")

    if len(normalized) > MAX_CONVERSATION_TITLE_LENGTH:
        raise ValueError(f"titulo no puede superar {MAX_CONVERSATION_TITLE_LENGTH} caracteres.")

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


def _to_conversation(
    row: Any,
) -> Conversation:
    return Conversation(
        id=row[0],
        usuario_id=row[1],
        titulo=row[2],
        fecha_inicio=row[3],
        fecha_actualizacion=row[4],
    )
