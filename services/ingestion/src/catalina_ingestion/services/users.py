from collections.abc import Callable
from typing import Any

from catalina_ingestion.db.postgres import (
    postgres_connection,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
    User,
)
from catalina_ingestion.domain.exceptions import (
    ForbiddenError,
    InvalidCurrentPasswordError,
    UserNotFoundError,
)
from catalina_ingestion.repositories.users import (
    UserRepository,
)
from catalina_ingestion.security.passwords import (
    PasswordService,
)

ALLOWED_ROLES = {
    "usuario",
    "administrador",
}


class UserService:
    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        password_service: PasswordService | None = None,
        connection_factory: Callable[
            [],
            Any,
        ] = postgres_connection,
    ) -> None:
        self.users = user_repository or UserRepository()

        self.passwords = password_service or PasswordService()

        self.connection_factory = connection_factory

    @staticmethod
    def require_admin(
        current_user: AuthenticatedUser,
    ) -> None:
        if current_user.rol != "administrador":
            raise ForbiddenError

    async def update_own_name(
        self,
        *,
        current_user: AuthenticatedUser,
        nombre: str,
    ) -> User:
        async with self.connection_factory() as connection:
            async with connection.transaction():
                user = await self.users.update_name(
                    connection,
                    current_user.id,
                    nombre,
                )

        if user is None:
            raise UserNotFoundError

        return user

    async def change_own_password(
        self,
        *,
        current_user: AuthenticatedUser,
        current_password: str,
        new_password: str,
    ) -> None:
        async with self.connection_factory() as connection:
            async with connection.transaction():
                user = await self.users.get_by_id(
                    connection,
                    current_user.id,
                )

                if user is None:
                    raise UserNotFoundError

                verification = self.passwords.verify_and_update(
                    current_password,
                    user.password_hash,
                )

                if not verification.valid:
                    raise InvalidCurrentPasswordError

                new_hash = self.passwords.hash_password(new_password)

                updated = await self.users.update_password_hash(
                    connection,
                    user.id,
                    new_hash,
                )

                if updated is None:
                    raise UserNotFoundError

    async def list_users(
        self,
        *,
        current_user: AuthenticatedUser,
        limit: int,
        offset: int,
    ) -> list[User]:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            return await self.users.list_users(
                connection,
                limit=limit,
                offset=offset,
            )

    async def get_user(
        self,
        *,
        current_user: AuthenticatedUser,
        user_id: int,
    ) -> User:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            user = await self.users.get_by_id(
                connection,
                user_id,
            )

        if user is None:
            raise UserNotFoundError

        return user

    async def set_user_active(
        self,
        *,
        current_user: AuthenticatedUser,
        user_id: int,
        active: bool,
    ) -> User:
        self.require_admin(current_user)

        async with self.connection_factory() as connection:
            async with connection.transaction():
                user = await self.users.set_active(
                    connection,
                    user_id,
                    active,
                )

        if user is None:
            raise UserNotFoundError

        return user

    async def set_user_role(
        self,
        *,
        current_user: AuthenticatedUser,
        user_id: int,
        role: str,
    ) -> User:
        self.require_admin(current_user)

        normalized_role = role.strip().lower()

        if normalized_role not in ALLOWED_ROLES:
            raise ValueError("Rol no soportado.")

        async with self.connection_factory() as connection:
            async with connection.transaction():
                user = await self.users.update_role(
                    connection,
                    user_id,
                    normalized_role,
                )

        if user is None:
            raise UserNotFoundError

        return user
