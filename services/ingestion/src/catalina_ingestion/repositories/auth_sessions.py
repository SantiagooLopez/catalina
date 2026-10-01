from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from catalina_ingestion.domain.auth import AuthSession


class AuthSessionRepository:
    async def create(
        self,
        connection: AsyncConnection[Any],
        *,
        user_id: int,
        refresh_token_hash: str,
        expires_at: datetime,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        self._validate_user_id(user_id)

        normalized_hash = self._normalize_refresh_hash(refresh_token_hash)

        cursor = await connection.execute(
            """
            INSERT INTO catalina.sesiones_auth (
                usuario_id,
                refresh_token_hash,
                fecha_expiracion,
                ip,
                user_agent
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING
                id,
                usuario_id,
                refresh_token_hash,
                fecha_creacion,
                fecha_expiracion,
                fecha_revocacion,
                ultima_rotacion,
                ip,
                user_agent
            """,
            (
                user_id,
                normalized_hash,
                expires_at,
                ip,
                user_agent,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear la sesión de autenticación.")

        return self._to_session(row)

    async def get_by_id(
        self,
        connection: AsyncConnection[Any],
        session_id: UUID,
    ) -> AuthSession | None:
        self._validate_session_id(session_id)

        cursor = await connection.execute(
            """
            SELECT
                id,
                usuario_id,
                refresh_token_hash,
                fecha_creacion,
                fecha_expiracion,
                fecha_revocacion,
                ultima_rotacion,
                ip,
                user_agent
            FROM catalina.sesiones_auth
            WHERE id = %s
            LIMIT 1
            """,
            (session_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_session(row)

    async def get_by_refresh_hash(
        self,
        connection: AsyncConnection[Any],
        refresh_token_hash: str,
    ) -> AuthSession | None:
        normalized_hash = self._normalize_refresh_hash(refresh_token_hash)

        cursor = await connection.execute(
            """
            SELECT
                id,
                usuario_id,
                refresh_token_hash,
                fecha_creacion,
                fecha_expiracion,
                fecha_revocacion,
                ultima_rotacion,
                ip,
                user_agent
            FROM catalina.sesiones_auth
            WHERE refresh_token_hash = %s
            LIMIT 1
            """,
            (normalized_hash,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_session(row)

    async def rotate_refresh_token(
        self,
        connection: AsyncConnection[Any],
        *,
        session_id: UUID,
        expected_refresh_token_hash: str,
        new_refresh_token_hash: str,
        expires_at: datetime,
    ) -> AuthSession | None:
        self._validate_session_id(session_id)

        expected_hash = self._normalize_refresh_hash(expected_refresh_token_hash)

        new_hash = self._normalize_refresh_hash(new_refresh_token_hash)

        cursor = await connection.execute(
            """
            UPDATE catalina.sesiones_auth
            SET refresh_token_hash = %s,
                fecha_expiracion = %s,
                ultima_rotacion = CURRENT_TIMESTAMP
            WHERE id = %s
              AND refresh_token_hash = %s
              AND fecha_revocacion IS NULL
              AND fecha_expiracion > CURRENT_TIMESTAMP
            RETURNING
                id,
                usuario_id,
                refresh_token_hash,
                fecha_creacion,
                fecha_expiracion,
                fecha_revocacion,
                ultima_rotacion,
                ip,
                user_agent
            """,
            (
                new_hash,
                expires_at,
                session_id,
                expected_hash,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_session(row)

    async def revoke(
        self,
        connection: AsyncConnection[Any],
        session_id: UUID,
    ) -> bool:
        self._validate_session_id(session_id)

        cursor = await connection.execute(
            """
            UPDATE catalina.sesiones_auth
            SET fecha_revocacion = CURRENT_TIMESTAMP
            WHERE id = %s
              AND fecha_revocacion IS NULL
            RETURNING id
            """,
            (session_id,),
        )

        row = await cursor.fetchone()

        return row is not None

    async def revoke_all_for_user(
        self,
        connection: AsyncConnection[Any],
        user_id: int,
    ) -> int:
        self._validate_user_id(user_id)

        cursor = await connection.execute(
            """
            UPDATE catalina.sesiones_auth
            SET fecha_revocacion = CURRENT_TIMESTAMP
            WHERE usuario_id = %s
              AND fecha_revocacion IS NULL
            """,
            (user_id,),
        )

        return cursor.rowcount

    async def delete_expired(
        self,
        connection: AsyncConnection[Any],
    ) -> int:
        cursor = await connection.execute(
            """
            DELETE FROM catalina.sesiones_auth
            WHERE fecha_expiracion
                <= CURRENT_TIMESTAMP
            """
        )

        return cursor.rowcount

    @staticmethod
    def _validate_user_id(
        user_id: int,
    ) -> None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

    @staticmethod
    def _validate_session_id(
        session_id: UUID,
    ) -> None:
        if not isinstance(
            session_id,
            UUID,
        ):
            raise TypeError("session_id debe ser UUID.")

    @staticmethod
    def _normalize_refresh_hash(
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError("refresh_token_hash debe ser texto.")

        normalized = value.strip().lower()

        valid = len(normalized) == 64 and all(
            character in "0123456789abcdef" for character in normalized
        )

        if not valid:
            raise ValueError("refresh_token_hash debe ser un SHA-256 hexadecimal de 64 caracteres.")

        return normalized

    @staticmethod
    def _to_session(
        row: tuple[Any, ...],
    ) -> AuthSession:
        return AuthSession(
            id=row[0],
            usuario_id=row[1],
            refresh_token_hash=row[2],
            fecha_creacion=row[3],
            fecha_expiracion=row[4],
            fecha_revocacion=row[5],
            ultima_rotacion=row[6],
            ip=row[7],
            user_agent=row[8],
        )
