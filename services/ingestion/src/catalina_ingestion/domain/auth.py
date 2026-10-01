from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: int
    email: str
    nombre: str
    rol: str
    password_hash: str
    activo: bool
    fecha_creacion: datetime | None
    fecha_actualizacion: datetime
    ultimo_acceso: datetime | None


@dataclass(frozen=True, slots=True)
class AuthSession:
    id: UUID
    usuario_id: int
    refresh_token_hash: str
    fecha_creacion: datetime
    fecha_expiracion: datetime
    fecha_revocacion: datetime | None
    ultima_rotacion: datetime | None
    ip: IPv4Address | IPv6Address | None
    user_agent: str | None

    @property
    def revoked(self) -> bool:
        return self.fecha_revocacion is not None

    def is_expired(
        self,
        *,
        now: datetime,
    ) -> bool:
        return self.fecha_expiracion <= now

    def is_active(
        self,
        *,
        now: datetime,
    ) -> bool:
        return not self.revoked and not self.is_expired(now=now)


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    user_id: int
    email: str
    nombre: str
    rol: str
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class TokenRefreshResult:
    user_id: int
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    email: str
    nombre: str
    rol: str
    activo: bool
