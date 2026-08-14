"""Testes do gerador criptograficamente seguro."""

import string

import pytest

from app.services.password_generator import SYMBOLS, PasswordOptions, generate_password


def test_default_length_and_all_categories() -> None:
    password = generate_password()

    assert len(password) == 20
    assert any(character in string.ascii_uppercase for character in password)
    assert any(character in string.ascii_lowercase for character in password)
    assert any(character in string.digits for character in password)
    assert any(character in SYMBOLS for character in password)


def test_selected_categories_only() -> None:
    password = generate_password(
        PasswordOptions(
            length=48,
            uppercase=False,
            lowercase=True,
            digits=True,
            symbols=False,
        )
    )

    assert len(password) == 48
    assert set(password) <= set(string.ascii_lowercase + string.digits)
    assert any(character in string.ascii_lowercase for character in password)
    assert any(character in string.digits for character in password)


def test_rejects_no_categories() -> None:
    with pytest.raises(ValueError):
        generate_password(
            PasswordOptions(
                uppercase=False,
                lowercase=False,
                digits=False,
                symbols=False,
            )
        )
