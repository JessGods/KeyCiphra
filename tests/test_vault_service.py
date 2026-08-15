"""Testes de criação e desbloqueio persistente do cofre."""

import sqlite3
from pathlib import Path

import pytest

from app.security.kdf import KDFParameters
from app.services.vault_service import (
    VaultAlreadyExistsError,
    VaultService,
    VaultUnlockError,
)

FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


def test_create_persists_and_unlocks_with_new_service(tmp_path: Path) -> None:
    database_path = tmp_path / "vault.db"
    service = VaultService(database_path)

    initial_session = service.create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    initial_session.lock()

    reopened_service = VaultService(database_path)
    reopened_session = reopened_service.unlock(MASTER_PASSWORD)

    assert database_path.is_file()
    assert reopened_service.exists()
    assert reopened_session.is_unlocked


def test_wrong_master_password_does_not_unlock(tmp_path: Path) -> None:
    service = VaultService(tmp_path / "vault.db")
    service.create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()

    with pytest.raises(VaultUnlockError):
        service.unlock("outra-frase-mestra-ficticia")


def test_master_password_is_not_stored_in_database(tmp_path: Path) -> None:
    database_path = tmp_path / "vault.db"
    VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()

    assert MASTER_PASSWORD.encode("utf-8") not in database_path.read_bytes()


def test_refuses_to_overwrite_existing_vault(tmp_path: Path) -> None:
    service = VaultService(tmp_path / "vault.db")
    service.create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()

    with pytest.raises(VaultAlreadyExistsError):
        service.create("segunda-frase-mestra-ficticia", FAST_TEST_PARAMETERS)


def test_modified_verifier_does_not_unlock(tmp_path: Path) -> None:
    database_path = tmp_path / "vault.db"
    service = VaultService(database_path)
    service.create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()

    with sqlite3.connect(database_path) as connection:
        ciphertext = connection.execute(
            "SELECT verifier_ciphertext FROM vault_metadata WHERE singleton = 1"
        ).fetchone()[0]
        modified = bytearray(ciphertext)
        modified[0] ^= 1
        connection.execute(
            "UPDATE vault_metadata SET verifier_ciphertext = ? WHERE singleton = 1",
            (bytes(modified),),
        )

    with pytest.raises(VaultUnlockError):
        service.unlock(MASTER_PASSWORD)


def test_rejects_short_master_password(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        VaultService(tmp_path / "vault.db").create("curta", FAST_TEST_PARAMETERS)
