"""Testes da derivação Argon2id."""

import pytest

from app.security.kdf import KDFParameters, derive_key, generate_salt

FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)


def test_same_password_and_salt_produce_same_key() -> None:
    salt = generate_salt()

    first = derive_key("frase mestra fictícia", salt, FAST_TEST_PARAMETERS)
    second = derive_key("frase mestra fictícia", salt, FAST_TEST_PARAMETERS)

    assert first == second
    assert len(first) == 32


def test_different_salts_produce_different_keys() -> None:
    first = derive_key("frase mestra fictícia", generate_salt(), FAST_TEST_PARAMETERS)
    second = derive_key("frase mestra fictícia", generate_salt(), FAST_TEST_PARAMETERS)

    assert first != second


def test_different_passwords_produce_different_keys() -> None:
    salt = generate_salt()

    first = derive_key("primeira frase fictícia", salt, FAST_TEST_PARAMETERS)
    second = derive_key("segunda frase fictícia", salt, FAST_TEST_PARAMETERS)

    assert first != second


def test_salt_is_random_and_has_expected_length() -> None:
    first = generate_salt()
    second = generate_salt()

    assert len(first) == 16
    assert first != second


def test_rejects_empty_master_password() -> None:
    with pytest.raises(ValueError):
        derive_key("", generate_salt(), FAST_TEST_PARAMETERS)


def test_rejects_short_salt() -> None:
    with pytest.raises(ValueError):
        derive_key("frase fictícia", b"salt curto", FAST_TEST_PARAMETERS)


@pytest.mark.parametrize(
    "parameters",
    (
        {"time_cost": 11},
        {"memory_cost_kib": (256 * 1_024) + 1},
        {"parallelism": 17},
    ),
)
def test_rejects_untrusted_resource_exhaustion_parameters(parameters: dict) -> None:
    with pytest.raises(ValueError):
        KDFParameters(**parameters)
