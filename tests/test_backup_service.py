"""Testes dos snapshots criptografados do cofre."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.credential import Credential
from app.repositories.credential_repository import CredentialRepository
from app.security.kdf import KDFParameters
from app.services.backup_service import (
    BackupAuthenticationError,
    BackupError,
    BackupService,
)
from app.services.vault_service import VaultService


FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


def test_backup_reopens_and_contains_no_sensitive_plaintext(tmp_path: Path) -> None:
    vault_path = tmp_path / "data" / "vault.db"
    backup_directory = tmp_path / "backups"
    session = VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credential = Credential.create(
        title="Serviço ultrassecreto fictício",
        username="usuario-secreto@example.invalid",
        password="senha-ficticia-nao-real",
        notes="nota confidencial fictícia",
    )
    CredentialRepository(vault_path, session).add(credential)

    backup = BackupService(vault_path, backup_directory).create_backup()
    restored_session = VaultService(backup).unlock(MASTER_PASSWORD)
    restored = CredentialRepository(backup, restored_session).get(credential.id)

    assert restored == credential
    backup_bytes = backup.read_bytes()
    for sensitive in (
        credential.title,
        credential.username,
        credential.password,
        credential.notes,
    ):
        assert sensitive.encode("utf-8") not in backup_bytes


def test_automatic_backup_respects_minimum_interval(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault.db"
    service = BackupService(vault_path, tmp_path / "backups")
    VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    now = datetime.now(UTC)

    backup = service.create_backup(now)
    os.utime(backup, (now.timestamp(), now.timestamp()))

    assert service.create_if_due(now=now + timedelta(hours=23)) is None
    assert service.create_if_due(now=now + timedelta(hours=25)) is not None


def test_retention_keeps_only_configured_number(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault.db"
    VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    service = BackupService(vault_path, tmp_path / "backups", retention=3)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    for offset in range(5):
        service.create_backup(start + timedelta(seconds=offset))

    assert len(service.list_backups()) == 3


def test_invalid_database_fails_securely(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault.db"
    vault_path.write_bytes(b"arquivo invalido ficticio")

    with pytest.raises(BackupError):
        BackupService(vault_path, tmp_path / "backups").create_backup()

    assert not list((tmp_path / "backups").glob("*.tmp"))


def test_exported_vault_can_be_opened_elsewhere(tmp_path: Path) -> None:
    vault_path = tmp_path / "data" / "vault.db"
    session = VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credential = Credential.create(title="Conta exportada", password="segredo-ficticio")
    CredentialRepository(vault_path, session).add(credential)
    destination = tmp_path / "transferencia" / "keyciphra.db"

    exported = BackupService(vault_path, tmp_path / "backups").export_backup(destination)

    imported_session = VaultService(exported).unlock(MASTER_PASSWORD)
    assert CredentialRepository(exported, imported_session).get(credential.id) == credential


def test_restore_authenticates_and_preserves_previous_vault(tmp_path: Path) -> None:
    vault_path = tmp_path / "data" / "vault.db"
    current_session = VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    current = Credential.create(title="Cofre atual", password="atual-ficticia")
    CredentialRepository(vault_path, current_session).add(current)

    imported_path = tmp_path / "received" / "other-vault.db"
    imported_session = VaultService(imported_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    imported = Credential.create(title="Cofre importado", password="importada-ficticia")
    CredentialRepository(imported_path, imported_session).add(imported)

    service = BackupService(vault_path, tmp_path / "backups")
    safety_backup = service.restore_backup(imported_path, MASTER_PASSWORD)

    restored_session = VaultService(vault_path).unlock(MASTER_PASSWORD)
    assert CredentialRepository(vault_path, restored_session).get(imported.id) == imported
    safety_session = VaultService(safety_backup).unlock(MASTER_PASSWORD)
    assert CredentialRepository(safety_backup, safety_session).get(current.id) == current


def test_restore_rejects_wrong_password_without_changing_current_vault(tmp_path: Path) -> None:
    vault_path = tmp_path / "data" / "vault.db"
    VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    imported_path = tmp_path / "received.db"
    VaultService(imported_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    original_bytes = vault_path.read_bytes()
    service = BackupService(vault_path, tmp_path / "backups")

    with pytest.raises(BackupAuthenticationError):
        service.restore_backup(imported_path, "senha-mestra-incorreta")

    assert vault_path.read_bytes() == original_bytes
    assert service.list_backups() == []


def test_restore_rejects_tampered_credential(tmp_path: Path) -> None:
    vault_path = tmp_path / "data" / "vault.db"
    VaultService(vault_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    imported_path = tmp_path / "received.db"
    imported_session = VaultService(imported_path).create(
        MASTER_PASSWORD,
        FAST_TEST_PARAMETERS,
    )
    CredentialRepository(imported_path, imported_session).add(
        Credential.create(title="Registro adulterado", password="ficticia")
    )
    with sqlite3.connect(imported_path) as connection:
        connection.execute("UPDATE credentials SET payload_ciphertext = zeroblob(32)")

    with pytest.raises(BackupAuthenticationError):
        BackupService(vault_path, tmp_path / "backups").restore_backup(
            imported_path,
            MASTER_PASSWORD,
        )
