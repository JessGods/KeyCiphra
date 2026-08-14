"""Testes da migração não destrutiva para a pasta do usuário."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.credential import Credential
from app.repositories.credential_repository import CredentialRepository
from app.security.kdf import KDFParameters
from app.services.backup_service import BackupService
from app.services.storage_migration_service import (
    StorageMigrationError,
    migrate_legacy_storage,
)
from app.services.vault_service import VaultService


FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


def test_migration_copies_vault_and_backups_without_removing_originals(
    tmp_path: Path,
) -> None:
    legacy_vault = tmp_path / "project" / "data" / "vault.db"
    legacy_backups = tmp_path / "project" / "backups"
    session = VaultService(legacy_vault).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credential = Credential.create(title="Conta migrada", password="segredo-ficticio")
    CredentialRepository(legacy_vault, session).add(credential)
    original_backup = BackupService(legacy_vault, legacy_backups).create_backup()
    target_vault = tmp_path / "local-app-data" / "data" / "vault.db"
    target_backups = tmp_path / "local-app-data" / "backups"

    result = migrate_legacy_storage(
        legacy_vault,
        legacy_backups,
        target_vault,
        target_backups,
    )

    assert result.vault_copied
    assert result.backups_copied == 1
    assert result.backups_skipped == 0
    assert legacy_vault.exists()
    assert original_backup.exists()
    restored_session = VaultService(target_vault).unlock(MASTER_PASSWORD)
    assert CredentialRepository(target_vault, restored_session).get(credential.id) == credential
    assert (target_backups / original_backup.name).is_file()


def test_migration_never_overwrites_existing_target(tmp_path: Path) -> None:
    legacy_vault = tmp_path / "legacy.db"
    target_vault = tmp_path / "target" / "vault.db"
    VaultService(legacy_vault).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    target_password = "outra-frase-mestra-ficticia"
    VaultService(target_vault).create(target_password, FAST_TEST_PARAMETERS).lock()
    original_target = target_vault.read_bytes()

    result = migrate_legacy_storage(
        legacy_vault,
        tmp_path / "legacy-backups",
        target_vault,
        tmp_path / "target-backups",
    )

    assert not result.vault_copied
    assert target_vault.read_bytes() == original_target
    VaultService(target_vault).unlock(target_password).lock()


def test_invalid_legacy_vault_fails_without_creating_target(tmp_path: Path) -> None:
    legacy_vault = tmp_path / "legacy.db"
    legacy_vault.write_bytes(b"arquivo-invalido-ficticio")
    target_vault = tmp_path / "target" / "vault.db"

    with pytest.raises(StorageMigrationError):
        migrate_legacy_storage(
            legacy_vault,
            tmp_path / "legacy-backups",
            target_vault,
            tmp_path / "target-backups",
        )

    assert not target_vault.exists()
