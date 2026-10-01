from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    Mock,
)
from uuid import UUID

import pytest

import catalina_ingestion.services.auth as auth_module
from catalina_ingestion.domain.auth import (
    AuthSession,
    User,
)
from catalina_ingestion.domain.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from catalina_ingestion.security.passwords import (
    PasswordVerification,
)
from catalina_ingestion.security.tokens import (
    AccessTokenClaims,
    RefreshToken,
    TokenValidationError,
)
from catalina_ingestion.services.auth import (
    AuthService,
)


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False


class FakeConnection:
    def transaction(self):
        return AsyncContext(None)


class FakePool:
    def __init__(self):
        self.connection_value = FakeConnection()

    def connection(self):
        return AsyncContext(self.connection_value)


def create_user(
    *,
    active: bool = True,
    password_hash: str = "stored-hash",
) -> User:
    return User(
        id=7,
        email="usuario@ucatolica.edu.co",
        nombre="Usuario Catalina",
        rol="usuario",
        password_hash=password_hash,
        activo=active,
        fecha_creacion=datetime(
            2026,
            10,
            1,
            1,
            0,
        ),
        fecha_actualizacion=datetime(
            2026,
            10,
            1,
            1,
            0,
            tzinfo=UTC,
        ),
        ultimo_acceso=None,
    )


def create_dependencies(
    user: User | None,
):
    users = SimpleNamespace(
        get_by_email=AsyncMock(return_value=user),
        update_password_hash=AsyncMock(return_value=user),
        update_last_access=AsyncMock(return_value=user),
    )

    sessions = SimpleNamespace(
        create=AsyncMock(),
        get_by_refresh_hash=AsyncMock(),
        rotate_refresh_token=AsyncMock(),
    )

    passwords = SimpleNamespace(
        hash_password=Mock(return_value="dummy-hash"),
        verify_and_update=Mock(
            return_value=(
                PasswordVerification(
                    valid=True,
                    updated_hash=None,
                )
            )
        ),
    )

    refresh = RefreshToken(
        token="refresh-token",
        token_hash="a" * 64,
        expires_at=(datetime.now(UTC) + timedelta(days=7)),
    )

    tokens = SimpleNamespace(
        create_access_token=Mock(return_value="access-token"),
        create_refresh_token=Mock(return_value=refresh),
    )

    return (
        users,
        sessions,
        passwords,
        tokens,
        refresh,
    )


@pytest.mark.asyncio
async def test_authenticate_success(
    monkeypatch,
):
    user = create_user()

    (
        users,
        sessions,
        passwords,
        tokens,
        refresh,
    ) = create_dependencies(user)

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.authenticate(
        email="usuario@ucatolica.edu.co",
        password="secreto",
        ip="127.0.0.1",
        user_agent="pytest",
    )

    assert result.user_id == 7

    assert result.email == "usuario@ucatolica.edu.co"

    assert result.rol == "usuario"
    assert result.access_token == "access-token"

    assert result.refresh_token == "refresh-token"

    users.get_by_email.assert_awaited_once()

    sessions.create.assert_awaited_once_with(
        pool.connection_value,
        user_id=7,
        refresh_token_hash=(refresh.token_hash),
        expires_at=refresh.expires_at,
        ip="127.0.0.1",
        user_agent="pytest",
    )

    users.update_last_access.assert_awaited_once_with(
        pool.connection_value,
        7,
    )


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_password(
    monkeypatch,
):
    user = create_user()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    passwords.verify_and_update.return_value = PasswordVerification(
        valid=False,
    )

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidCredentialsError,
    ) as error:
        await service.authenticate(
            email=user.email,
            password="incorrecta",
        )

    assert error.value.code == "INVALID_CREDENTIALS"

    sessions.create.assert_not_awaited()
    users.update_last_access.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_missing_user_uses_dummy_hash(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    passwords.verify_and_update.return_value = PasswordVerification(
        valid=False,
    )

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidCredentialsError,
    ):
        await service.authenticate(
            email="noexiste@ucatolica.edu.co",
            password="secreto",
        )

    passwords.verify_and_update.assert_called_once_with(
        "secreto",
        "dummy-hash",
    )

    sessions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_rejects_inactive_user(
    monkeypatch,
):
    user = create_user(active=False)

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidCredentialsError,
    ) as error:
        await service.authenticate(
            email=user.email,
            password="secreto",
        )

    assert error.value.code == "INVALID_CREDENTIALS"

    passwords.verify_and_update.assert_called_once()

    sessions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_updates_old_password_hash(
    monkeypatch,
):
    user = create_user(password_hash="old-hash")

    updated_user = create_user(password_hash="new-hash")

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    passwords.verify_and_update.return_value = PasswordVerification(
        valid=True,
        updated_hash="new-hash",
    )

    users.update_password_hash.return_value = updated_user

    users.update_last_access.return_value = updated_user

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.authenticate(
        email=user.email,
        password="secreto",
    )

    assert result.user_id == 7

    users.update_password_hash.assert_awaited_once_with(
        pool.connection_value,
        7,
        "new-hash",
    )


@pytest.mark.asyncio
async def test_authenticate_rejects_blank_credentials(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidCredentialsError,
    ):
        await service.authenticate(
            email="   ",
            password="",
        )

    users.get_by_email.assert_not_awaited()
    sessions.create.assert_not_awaited()


def create_auth_session(
    *,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> AuthSession:
    now = datetime.now(UTC)

    return AuthSession(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        usuario_id=7,
        refresh_token_hash="a" * 64,
        fecha_creacion=now,
        fecha_expiracion=(expires_at or now + timedelta(days=7)),
        fecha_revocacion=revoked_at,
        ultima_rotacion=None,
        ip=None,
        user_agent=None,
    )


@pytest.mark.asyncio
async def test_refresh_success(
    monkeypatch,
):
    user = create_user()
    session = create_auth_session()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    new_refresh = RefreshToken(
        token="new-refresh-token",
        token_hash="b" * 64,
        expires_at=(datetime.now(UTC) + timedelta(days=7)),
    )

    users.get_by_id = AsyncMock(return_value=user)

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    rotated_session = create_auth_session()
    sessions.rotate_refresh_token = AsyncMock(return_value=rotated_session)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    tokens.verify_refresh_token = Mock(return_value=True)

    tokens.create_refresh_token = Mock(return_value=new_refresh)

    tokens.create_access_token = Mock(return_value="new-access-token")

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.refresh(refresh_token="old-refresh-token")

    assert result.user_id == 7

    assert result.access_token == "new-access-token"

    assert result.refresh_token == "new-refresh-token"

    sessions.get_by_refresh_hash.assert_awaited_once_with(
        pool.connection_value,
        "a" * 64,
    )

    sessions.rotate_refresh_token.assert_awaited_once_with(
        pool.connection_value,
        session_id=session.id,
        expected_refresh_token_hash=(session.refresh_token_hash),
        new_refresh_token_hash=(new_refresh.token_hash),
        expires_at=new_refresh.expires_at,
    )

    tokens.create_access_token.assert_called_once_with(
        user_id=7,
        role="usuario",
    )


@pytest.mark.asyncio
async def test_refresh_rejects_blank_token(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="   ")


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_token(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    sessions.get_by_refresh_hash = AsyncMock(return_value=None)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="unknown-token")


@pytest.mark.asyncio
async def test_refresh_rejects_expired_session(
    monkeypatch,
):
    session = create_auth_session(expires_at=(datetime.now(UTC) - timedelta(seconds=1)))

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(create_user())

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="expired-token")


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_session(
    monkeypatch,
):
    now = datetime.now(UTC)

    session = create_auth_session(revoked_at=now)

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(create_user())

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="revoked-token")


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(
    monkeypatch,
):
    user = create_user(active=False)

    session = create_auth_session()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    users.get_by_id = AsyncMock(return_value=user)

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    tokens.verify_refresh_token = Mock(return_value=True)

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="refresh-token")

    sessions.rotate_refresh_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_rejects_replayed_token(
    monkeypatch,
):
    user = create_user()
    session = create_auth_session()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    users.get_by_id = AsyncMock(return_value=user)

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    sessions.rotate_refresh_token = AsyncMock(return_value=None)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    tokens.verify_refresh_token = Mock(return_value=True)

    tokens.create_refresh_token = Mock(
        return_value=RefreshToken(
            token="new-token",
            token_hash="b" * 64,
            expires_at=(datetime.now(UTC) + timedelta(days=7)),
        )
    )

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidRefreshTokenError,
    ):
        await service.refresh(refresh_token="old-token")

    tokens.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_logout_revokes_session(
    monkeypatch,
):
    user = create_user()
    session = create_auth_session()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    sessions.get_by_refresh_hash = AsyncMock(return_value=session)

    sessions.revoke = AsyncMock(return_value=True)

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.logout(refresh_token="refresh-token")

    assert result is True

    sessions.revoke.assert_awaited_once_with(
        pool.connection_value,
        session.id,
    )


@pytest.mark.asyncio
async def test_logout_unknown_token_is_idempotent(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    tokens.hash_refresh_token = Mock(return_value="a" * 64)

    sessions.get_by_refresh_hash = AsyncMock(return_value=None)

    sessions.revoke = AsyncMock()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.logout(refresh_token="unknown-token")

    assert result is False

    sessions.revoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_blank_token_returns_false(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.logout(refresh_token="   ")

    assert result is False


@pytest.mark.asyncio
async def test_get_current_user_success(
    monkeypatch,
):
    user = create_user()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    claims = AccessTokenClaims(
        user_id=7,
        role="usuario",
        token_id="test-token-id",
        issued_at=datetime.now(UTC),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)),
    )

    tokens.decode_access_token = Mock(return_value=claims)

    users.get_by_id = AsyncMock(return_value=user)

    pool = FakePool()

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: pool,
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    result = await service.get_current_user(access_token="access-token")

    assert result.id == 7

    assert result.email == "usuario@ucatolica.edu.co"

    assert result.rol == "usuario"
    assert result.activo is True

    users.get_by_id.assert_awaited_once_with(
        pool.connection_value,
        7,
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    tokens.decode_access_token = Mock(side_effect=TokenValidationError("token inválido"))

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidAccessTokenError,
    ):
        await service.get_current_user(access_token="invalid-token")


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user(
    monkeypatch,
):
    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(None)

    claims = AccessTokenClaims(
        user_id=7,
        role="usuario",
        token_id="test-token-id",
        issued_at=datetime.now(UTC),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)),
    )

    tokens.decode_access_token = Mock(return_value=claims)

    users.get_by_id = AsyncMock(return_value=None)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidAccessTokenError,
    ):
        await service.get_current_user(access_token="access-token")


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user(
    monkeypatch,
):
    user = create_user(active=False)

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    claims = AccessTokenClaims(
        user_id=7,
        role="usuario",
        token_id="test-token-id",
        issued_at=datetime.now(UTC),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)),
    )

    tokens.decode_access_token = Mock(return_value=claims)

    users.get_by_id = AsyncMock(return_value=user)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidAccessTokenError,
    ):
        await service.get_current_user(access_token="access-token")


@pytest.mark.asyncio
async def test_get_current_user_rejects_changed_role(
    monkeypatch,
):
    user = create_user()

    (
        users,
        sessions,
        passwords,
        tokens,
        _,
    ) = create_dependencies(user)

    claims = AccessTokenClaims(
        user_id=7,
        role="administrador",
        token_id="test-token-id",
        issued_at=datetime.now(UTC),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)),
    )

    tokens.decode_access_token = Mock(return_value=claims)

    users.get_by_id = AsyncMock(return_value=user)

    monkeypatch.setattr(
        auth_module,
        "get_postgres_pool",
        lambda: FakePool(),
    )

    service = AuthService(
        user_repository=users,
        session_repository=sessions,
        password_service=passwords,
        token_service=tokens,
    )

    with pytest.raises(
        InvalidAccessTokenError,
    ):
        await service.get_current_user(access_token="access-token")
