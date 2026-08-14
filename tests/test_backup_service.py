"""Testes dos snapshots criptografados do cofre."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.credential import Credential
from app.repositories.credential_repository import CredentialRepository
from app.security.kdf import KDFParameters
from app.services.backup_service import BackupError, BackupService
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
