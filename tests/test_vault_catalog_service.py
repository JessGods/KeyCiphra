"""Testes do catálogo e isolamento de múltiplos cofres."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.security.kdf import KDFParameters
from app.services.vault_catalog_service import (
    VaultArchiveAuthenticationError,
    VaultCatalogError,
    VaultCatalogService,
    VaultNameError,
)
from app.services.vault_service import VaultService

MASTER_PASSWORD = "frase-mestra-ficticia-longa"
FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)


def _service(tmp_path: Path) -> VaultCatalogService:
    return VaultCatalogService(
        tmp_path / "vaults.json",
        tmp_path / "vaults",
        tmp_path / "archived-vaults",
        tmp_path / "data" / "vault.db",
        tmp_path / "backups",
    )


def test_existing_vault_is_registered_once_without_being_moved(tmp_path: Path) -> None:
    legacy_path = tmp_path / "data" / "vault.db"
    VaultService(legacy_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    service = _service(tmp_path)

    first = service.initialize()
    reloaded = _service(tmp_path).initialize()

    assert len(first) == len(reloaded) == 1
    assert first[0] == reloaded[0]
    assert first[0].name == "Cofre principal"
    assert service.vault_path(first[0]) == legacy_path
    assert legacy_path.is_file()


def test_new_vault_has_isolated_database_and_backup_directory(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.initialize()

    vault, session = service.create(
        "Trabalho",
        MASTER_PASSWORD,
        FAST_TEST_PARAMETERS,
    )
    session.lock()

    database_path = service.vault_path(vault)
    assert database_path == tmp_path / "vaults" / vault.id / "vault.db"
    assert service.backup_directory(vault) == tmp_path / "vaults" / vault.id / "backups"
    assert VaultService(database_path).unlock(MASTER_PASSWORD).is_unlocked
    assert _service(tmp_path).get(vault.id) == vault


def test_names_are_unique_and_renamed_atomically(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first, session = service.create("Pessoal", MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    session.lock()
    second, session = service.create("Trabalho", MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    session.lock()

    with pytest.raises(VaultNameError):
        service.rename(second.id, " pessoal ")

    renamed = service.rename(first.id, "Família")
    assert renamed.name == "Família"
    assert _service(tmp_path).get(first.id).name == "Família"


def test_archive_requires_password_and_moves_managed_storage(tmp_path: Path) -> None:
    service = _service(tmp_path)
    vault, session = service.create("Temporário", MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    session.lock()
    original_directory = service.vault_path(vault).parent

    with pytest.raises(VaultArchiveAuthenticationError):
        service.archive(vault.id, "senha-incorreta-ficticia")

    assert original_directory.is_dir()
    assert service.get(vault.id) == vault

    archived = service.archive(vault.id, MASTER_PASSWORD)

    assert not original_directory.exists()
    assert (archived / "storage" / "vault.db").is_file()
    assert service.list_vaults() == ()
    with pytest.raises(VaultCatalogError):
        service.get(vault.id)


def test_invalid_catalog_is_rejected_without_touching_vault(tmp_path: Path) -> None:
    legacy_path = tmp_path / "data" / "vault.db"
    VaultService(legacy_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS).lock()
    catalog = tmp_path / "vaults.json"
    catalog.write_text(json.dumps({"version": 99, "vaults": []}), encoding="utf-8")

    with pytest.raises(VaultCatalogError):
        _service(tmp_path).initialize()

    assert legacy_path.is_file()
    VaultService(legacy_path).unlock(MASTER_PASSWORD).lock()
