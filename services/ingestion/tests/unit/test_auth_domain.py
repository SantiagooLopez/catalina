from datetime import UTC, datetime, timedelta
from uuid import UUID

from catalina_ingestion.domain.auth import (
    AuthSession,
)


def create_session(
    *,
    expires_at: datetime,
    revoked_at: datetime | None = None,
) -> AuthSession:
    return AuthSession(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        usuario_id=7,
        refresh_token_hash="a" * 64,
        fecha_creacion=datetime(
            2026,
            10,
            1,
            1,
            0,
            tzinfo=UTC,
        ),
        fecha_expiracion=expires_at,
        fecha_revocacion=revoked_at,
        ultima_rotacion=None,
        ip=None,
        user_agent=None,
    )


def test_auth_session_is_active():
    now = datetime.now(UTC)

    session = create_session(expires_at=(now + timedelta(days=1)))

    assert session.revoked is False
    assert session.is_expired(now=now) is False

    assert session.is_active(now=now) is True


def test_auth_session_is_expired():
    now = datetime.now(UTC)

    session = create_session(expires_at=(now - timedelta(seconds=1)))

    assert session.is_expired(now=now) is True

    assert session.is_active(now=now) is False


def test_auth_session_is_revoked():
    now = datetime.now(UTC)

    session = create_session(
        expires_at=(now + timedelta(days=1)),
        revoked_at=now,
    )

    assert session.revoked is True

    assert session.is_active(now=now) is False
