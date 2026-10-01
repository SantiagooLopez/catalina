from typing import Any

from psycopg import AsyncConnection

from catalina_ingestion.domain.auth import User


class UserRepository:
    async def create(
        self,
        connection: AsyncConnection[Any],
        *,
        email: str,
        nombre: str,
        rol: str,
        password_hash: str,
    ) -> User:
        normalized_email = self._normalize_email(email)
        normalized_name = self._normalize_required(
            nombre,
            field_name="nombre",
        )
        normalized_role = self._normalize_required(
            rol,
            field_name="rol",
        ).lower()
        normalized_password_hash = self._normalize_required(
            password_hash,
            field_name="password_hash",
        )

        cursor = await connection.execute(
            """
            INSERT INTO catalina.usuarios (
                email,
                nombre,
                rol,
                password_hash
            )
            VALUES (%s, %s, %s, %s)
            RETURNING
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            """,
            (
                normalized_email,
                normalized_name,
                normalized_role,
                normalized_password_hash,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("No fue posible crear el usuario.")

        return self._to_user(row)

    async def get_by_id(
        self,
        connection: AsyncConnection[Any],
        user_id: int,
    ) -> User | None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

        cursor = await connection.execute(
            """
            SELECT
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            FROM catalina.usuarios
            WHERE id = %s
            LIMIT 1
            """,
            (user_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_user(row)

    async def get_by_email(
        self,
        connection: AsyncConnection[Any],
        email: str,
    ) -> User | None:
        normalized_email = self._normalize_email(email)

        cursor = await connection.execute(
            """
            SELECT
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            FROM catalina.usuarios
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (normalized_email,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_user(row)

    async def update_password_hash(
        self,
        connection: AsyncConnection[Any],
        user_id: int,
        password_hash: str,
    ) -> User | None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

        normalized_password_hash = self._normalize_required(
            password_hash,
            field_name="password_hash",
        )

        cursor = await connection.execute(
            """
            UPDATE catalina.usuarios
            SET password_hash = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            """,
            (
                normalized_password_hash,
                user_id,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_user(row)

    async def update_last_access(
        self,
        connection: AsyncConnection[Any],
        user_id: int,
    ) -> User | None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

        cursor = await connection.execute(
            """
            UPDATE catalina.usuarios
            SET ultimo_acceso = CURRENT_TIMESTAMP,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            """,
            (user_id,),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_user(row)

    async def set_active(
        self,
        connection: AsyncConnection[Any],
        user_id: int,
        active: bool,
    ) -> User | None:
        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id debe ser un entero positivo.")

        if not isinstance(active, bool):
            raise TypeError("active debe ser booleano.")

        cursor = await connection.execute(
            """
            UPDATE catalina.usuarios
            SET activo = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING
                id,
                email,
                nombre,
                rol,
                password_hash,
                activo,
                fecha_creacion,
                fecha_actualizacion,
                ultimo_acceso
            """,
            (
                active,
                user_id,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_user(row)

    @staticmethod
    def _normalize_email(
        email: str,
    ) -> str:
        if not isinstance(email, str):
            raise TypeError("email debe ser texto.")

        normalized = email.strip().lower()

        if not normalized:
            raise ValueError("email no puede estar vacío.")

        return normalized

    @staticmethod
    def _normalize_required(
        value: str,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} debe ser texto.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} no puede estar vacío.")

        return normalized

    @staticmethod
    def _to_user(
        row: tuple[Any, ...],
    ) -> User:
        return User(
            id=row[0],
            email=row[1],
            nombre=row[2],
            rol=row[3],
            password_hash=row[4],
            activo=row[5],
            fecha_creacion=row[6],
            fecha_actualizacion=row[7],
            ultimo_acceso=row[8],
        )
