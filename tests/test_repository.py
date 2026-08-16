"""Testes do CRUD criptografado de credenciais."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from app.models.credential import Credential
from app.repositories.credential_repository import (
    CredentialNotFoundError,
    CredentialRepository,
    RepositoryIntegrityError,
)
from app.security.kdf import KDFParameters
from app.security.session import VaultLockedError, VaultSession
from app.services.vault_service import VaultService

FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, VaultSession, CredentialRepository]:
    database_path = tmp_path / "vault.db"
    session = VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    return database_path, session, CredentialRepository(database_path, session)


def sample_credential() -> Credential:
    return Credential.create(
        title="Serviço Fictício",
        username="usuario.teste@example.invalid",
        password="senha-ficticia-nao-real-123",
        url="https://example.invalid/login",
        category="Testes",
        notes="Conteúdo fictício para teste de persistência.",
    )


def test_add_and_get_credential(
    repository: tuple[Path, VaultSession, CredentialRepository],
) -> None:
    _, _, repo = repository
    credential = sample_credential()

    repo.add(credential)

    assert repo.get(credential.id) == credential


def test_data_persists_after_lock_and_reopen(tmp_path: Path) -> None:
    database_path = tmp_path / "vault.db"
    vault = VaultService(database_path)
    first_session = vault.create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credential = sample_credential()
    CredentialRepository(database_path, first_session).add(credential)
    first_session.lock()

    reopened_session = VaultService(database_path).unlock(MASTER_PASSWORD)
    restored = CredentialRepository(database_path, reopened_session).get(credential.id)

    assert restored == credential


def test_list_update_and_delete(
    repository: tuple[Path, VaultSession, CredentialRepository],
) -> None:
    _, _, repo = repository
    first = sample_credential()
    second = Credential.create(title="Outro serviço", password="outro segredo fictício")
    repo.add(first)
    repo.add(second)

    assert {item.id for item in repo.list_all()} == {first.id, second.id}

    updated = repo.update(replace(first, title="Título atualizado"))
    assert repo.get(first.id).title == "Título atualizado"
    assert updated.updated_at >= first.updated_at

    repo.delete(second.id)
    with pytest.raises(CredentialNotFoundError):
        repo.get(second.id)


def test_sensitive_plaintext_is_not_persisted(
    repository: tuple[Path, VaultSession, CredentialRepository],
) -> None:
    database_path, _, repo = repository
    credential = sample_credential()
    repo.add(credential)
    database_bytes = database_path.read_bytes()

    for sensitive_value in (
        credential.title,
        credential.username,
        credential.password,
        credential.url,
        credential.category,
        credential.notes,
    ):
        assert sensitive_value.encode("utf-8") not in database_bytes


def test_modified_payload_is_detected(
    repository: tuple[Path, VaultSession, CredentialRepository],
) -> None:
    database_path, _, repo = repository
    credential = sample_credential()
    repo.add(credential)

    with closing(sqlite3.connect(database_path)) as connection, connection:
        ciphertext = connection.execute(
            "SELECT payload_ciphertext FROM credentials WHERE id = ?",
            (credential.id,),
        ).fetchone()[0]
        modified = bytearray(ciphertext)
        modified[0] ^= 1
        connection.execute(
            "UPDATE credentials SET payload_ciphertext = ? WHERE id = ?",
            (bytes(modified), credential.id),
        )

    with pytest.raises(RepositoryIntegrityError):
        repo.get(credential.id)


def test_locked_session_cannot_read_or_write(
    repository: tuple[Path, VaultSession, CredentialRepository],
) -> None:
    _, session, repo = repository
    session.lock()

    with pytest.raises(VaultLockedError):
        repo.add(sample_credential())
