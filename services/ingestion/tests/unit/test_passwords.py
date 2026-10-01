import pytest

from catalina_ingestion.security.passwords import (
    PasswordService,
)


def test_hash_password_uses_argon2():
    service = PasswordService()

    hashed = service.hash_password("Catalina-Segura-2026!")

    assert hashed != ("Catalina-Segura-2026!")

    assert hashed.startswith("$argon2")


def test_verify_password_returns_true_for_correct_password():
    service = PasswordService()

    password = "Catalina-Segura-2026!"
    hashed = service.hash_password(password)

    assert (
        service.verify_password(
            password,
            hashed,
        )
        is True
    )


def test_verify_password_returns_false_for_wrong_password():
    service = PasswordService()

    hashed = service.hash_password("Catalina-Segura-2026!")

    assert (
        service.verify_password(
            "incorrecta",
            hashed,
        )
        is False
    )


def test_verify_password_returns_false_for_invalid_hash():
    service = PasswordService()

    assert (
        service.verify_password(
            "Catalina-Segura-2026!",
            "hash-invalido",
        )
        is False
    )


def test_verify_and_update_returns_valid_result():
    service = PasswordService()

    password = "Catalina-Segura-2026!"
    hashed = service.hash_password(password)

    result = service.verify_and_update(
        password,
        hashed,
    )

    assert result.valid is True

    assert result.updated_hash is None or isinstance(
        result.updated_hash,
        str,
    )


def test_verify_and_update_returns_false_for_invalid_hash():
    service = PasswordService()

    result = service.verify_and_update(
        "Catalina-Segura-2026!",
        "hash-invalido",
    )

    assert result.valid is False
    assert result.updated_hash is None


def test_hash_password_rejects_empty_password():
    service = PasswordService()

    with pytest.raises(
        ValueError,
        match=("La contraseña no puede estar vacía"),
    ):
        service.hash_password("")


def test_hash_password_rejects_non_string_password():
    service = PasswordService()

    with pytest.raises(
        TypeError,
        match=("La contraseña debe ser texto"),
    ):
        service.hash_password(  # type: ignore[arg-type]
            123
        )
