from datetime import UTC, datetime

from catalina_ingestion.db.postgres import (
    get_postgres_pool,
)
from catalina_ingestion.domain.auth import (
    AuthenticatedUser,
    AuthenticationResult,
    TokenRefreshResult,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from catalina_ingestion.repositories.auth_sessions import (
    AuthSessionRepository,
)
from catalina_ingestion.repositories.users import (
    UserRepository,
)
from catalina_ingestion.security.passwords import (
    PasswordService,
)
from catalina_ingestion.security.tokens import (
    TokenService,
    TokenValidationError,
)


class AuthService:
    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        session_repository: AuthSessionRepository | None = None,
        password_service: PasswordService | None = None,
        token_service: TokenService | None = None,
    ) -> None:
        self.users = user_repository or UserRepository()

        self.sessions = session_repository or AuthSessionRepository()

        self.passwords = password_service or PasswordService()

        self.tokens = token_service or TokenService()

        self._dummy_password_hash = self.passwords.hash_password("catalina-auth-dummy-password")

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthenticationResult:
        if (
            not isinstance(email, str)
            or not email.strip()
            or not isinstance(password, str)
            or not password
        ):
            raise InvalidCredentialsError

        pool = get_postgres_pool()

        async with pool.connection() as connection:
            async with connection.transaction():
                user = await self.users.get_by_email(
                    connection,
                    email,
                )

                verification_hash = (
                    user.password_hash if user is not None else self._dummy_password_hash
                )

                verification = self.passwords.verify_and_update(
                    password,
                    verification_hash,
                )

                if user is None or not verification.valid or not user.activo:
                    raise InvalidCredentialsError

                if verification.updated_hash is not None:
                    updated_user = await self.users.update_password_hash(
                        connection,
                        user.id,
                        verification.updated_hash,
                    )

                    if updated_user is None:
                        raise RuntimeError("El usuario desapareció durante la autenticación.")

                    user = updated_user

                access_token = self.tokens.create_access_token(
                    user_id=user.id,
                    role=user.rol,
                )

                refresh_token = self.tokens.create_refresh_token()

                await self.sessions.create(
                    connection,
                    user_id=user.id,
                    refresh_token_hash=(refresh_token.token_hash),
                    expires_at=(refresh_token.expires_at),
                    ip=ip,
                    user_agent=user_agent,
                )

                accessed_user = await self.users.update_last_access(
                    connection,
                    user.id,
                )

                if accessed_user is None:
                    raise RuntimeError("El usuario desapareció durante la autenticación.")

                return AuthenticationResult(
                    user_id=accessed_user.id,
                    email=accessed_user.email,
                    nombre=accessed_user.nombre,
                    rol=accessed_user.rol,
                    access_token=access_token,
                    refresh_token=(refresh_token.token),
                    refresh_expires_at=(refresh_token.expires_at),
                )

    async def refresh(
        self,
        *,
        refresh_token: str,
    ) -> TokenRefreshResult:
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            raise InvalidRefreshTokenError

        refresh_hash = self.tokens.hash_refresh_token(refresh_token)

        pool = get_postgres_pool()

        async with pool.connection() as connection:
            async with connection.transaction():
                session = await self.sessions.get_by_refresh_hash(
                    connection,
                    refresh_hash,
                )

                if session is None:
                    raise InvalidRefreshTokenError

                now = datetime.now(UTC)

                if not session.is_active(now=now):
                    raise InvalidRefreshTokenError

                if not self.tokens.verify_refresh_token(
                    refresh_token,
                    session.refresh_token_hash,
                ):
                    raise InvalidRefreshTokenError

                user = await self.users.get_by_id(
                    connection,
                    session.usuario_id,
                )

                if user is None or not user.activo:
                    raise InvalidRefreshTokenError

                new_refresh = self.tokens.create_refresh_token()

                rotated = await self.sessions.rotate_refresh_token(
                    connection,
                    session_id=session.id,
                    expected_refresh_token_hash=(session.refresh_token_hash),
                    new_refresh_token_hash=(new_refresh.token_hash),
                    expires_at=(new_refresh.expires_at),
                )

                if rotated is None:
                    raise InvalidRefreshTokenError

                access_token = self.tokens.create_access_token(
                    user_id=user.id,
                    role=user.rol,
                )

                return TokenRefreshResult(
                    user_id=user.id,
                    access_token=access_token,
                    refresh_token=new_refresh.token,
                    refresh_expires_at=(new_refresh.expires_at),
                )

    async def logout(
        self,
        *,
        refresh_token: str,
    ) -> bool:
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return False

        refresh_hash = self.tokens.hash_refresh_token(refresh_token)

        pool = get_postgres_pool()

        async with pool.connection() as connection:
            async with connection.transaction():
                session = await self.sessions.get_by_refresh_hash(
                    connection,
                    refresh_hash,
                )

                if session is None:
                    return False

                return await self.sessions.revoke(
                    connection,
                    session.id,
                )

    async def get_current_user(
        self,
        *,
        access_token: str,
    ) -> AuthenticatedUser:
        if not isinstance(access_token, str) or not access_token.strip():
            raise InvalidAccessTokenError

        try:
            claims = self.tokens.decode_access_token(access_token)
        except TokenValidationError as error:
            raise InvalidAccessTokenError from error

        pool = get_postgres_pool()

        async with pool.connection() as connection:
            user = await self.users.get_by_id(
                connection,
                claims.user_id,
            )

        if user is None or not user.activo or user.rol != claims.role:
            raise InvalidAccessTokenError

        return AuthenticatedUser(
            id=user.id,
            email=user.email,
            nombre=user.nombre,
            rol=user.rol,
            activo=user.activo,
        )
