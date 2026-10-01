from dataclasses import dataclass

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    valid: bool
    updated_hash: str | None = None


class PasswordService:
    def __init__(
        self,
        password_hash: PasswordHash | None = None,
    ) -> None:
        self._password_hash = password_hash or PasswordHash.recommended()

    def hash_password(
        self,
        password: str,
    ) -> str:
        self._validate_password(password)

        return self._password_hash.hash(password)

    def verify_password(
        self,
        password: str,
        hashed_password: str,
    ) -> bool:
        if not password or not hashed_password:
            return False

        try:
            return self._password_hash.verify(
                password,
                hashed_password,
            )

        except UnknownHashError:
            return False

    def verify_and_update(
        self,
        password: str,
        hashed_password: str,
    ) -> PasswordVerification:
        if not password or not hashed_password:
            return PasswordVerification(valid=False)

        try:
            valid, updated_hash = self._password_hash.verify_and_update(
                password,
                hashed_password,
            )

        except UnknownHashError:
            return PasswordVerification(valid=False)

        return PasswordVerification(
            valid=valid,
            updated_hash=updated_hash,
        )

    @staticmethod
    def _validate_password(
        password: str,
    ) -> None:
        if not isinstance(password, str):
            raise TypeError("La contraseña debe ser texto.")

        if not password:
            raise ValueError("La contraseña no puede estar vacía.")
