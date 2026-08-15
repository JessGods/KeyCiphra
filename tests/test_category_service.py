"""Testes do catálogo criptografado e da reclassificação de categorias."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.models.category import Category
from app.models.credential import Credential
from app.repositories.category_repository import (
    CategoryRepository,
    CategoryRepositoryIntegrityError,
)
from app.repositories.credential_repository import CredentialRepository
from app.security.kdf import KDFParameters
from app.services.category_service import CategoryService, CategoryValidationError
from app.services.vault_service import VaultService, VaultUnlockError


FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


@pytest.fixture
def category_context(
    tmp_path: Path,
) -> tuple[Path, CategoryRepository, CredentialRepository, CategoryService]:
    database_path = tmp_path / "vault.db"
    session = VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credential_repository = CredentialRepository(database_path, session)
    category_repository = CategoryRepository(database_path, session)
    service = CategoryService(category_repository, credential_repository)
    return database_path, category_repository, credential_repository, service


def test_existing_credential_categories_are_migrated_without_duplicates(
    category_context: tuple[Path, CategoryRepository, CredentialRepository, CategoryService],
) -> None:
    _, _, credentials, service = category_context
    credentials.add(Credential.create(title="Primeira", category="Trabalho"))
    credentials.add(Credential.create(title="Segunda", category=" trabalho "))

    synchronized = service.synchronize(credentials.list_all())

    assert len(synchronized) == 1
    assert synchronized[0].name.casefold() == "trabalho"


def test_create_rejects_equivalent_duplicate_names(
    category_context: tuple[Path, CategoryRepository, CredentialRepository, CategoryService],
) -> None:
    _, _, _, service = category_context
    service.create("Financeiro")

    with pytest.raises(CategoryValidationError):
        service.create("  financeiro  ")


def test_rename_updates_every_related_credential(
    category_context: tuple[Path, CategoryRepository, CredentialRepository, CategoryService],
) -> None:
    _, _, credentials, service = category_context
    category = service.create("Pessoal")
    first = credentials.add(Credential.create(title="E-mail", category="Pessoal"))
    second = credentials.add(Credential.create(title="Fórum", category="pessoal"))

    service.rename(category.id, "Contas pessoais")

    assert credentials.get(first.id).category == "Contas pessoais"
    assert credentials.get(second.id).category == "Contas pessoais"


def test_delete_can_reassign_credentials_to_another_category(
    category_context: tuple[Path, CategoryRepository, CredentialRepository, CategoryService],
) -> None:
    _, categories, credentials, service = category_context
    old = service.create("Antiga")
    service.create("Nova")
    credential = credentials.add(Credential.create(title="Conta", category="Antiga"))

    changed = service.delete(old.id, "Nova")

    assert changed == 1
    assert credentials.get(credential.id).category == "Nova"
    assert [category.name for category in categories.list_all()] == ["Nova"]


def test_category_name_is_encrypted_and_tampering_is_detected(
    category_context: tuple[Path, CategoryRepository, CredentialRepository, CategoryService],
) -> None:
    database_path, categories, _, _ = category_context
    category = categories.add(Category.create("Categoria ultrassecreta fictícia"))
    assert category.name.encode("utf-8") not in database_path.read_bytes()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE categories SET payload_ciphertext = zeroblob(32) WHERE id = ?",
            (category.id,),
        )

    with pytest.raises(CategoryRepositoryIntegrityError):
        categories.get(category.id)


def test_old_vault_without_category_table_is_upgraded_non_destructively(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-vault.db"
    session = VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credentials = CredentialRepository(database_path, session)
    original = credentials.add(Credential.create(title="Conta antiga", category="Legado"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE categories")
        connection.execute("UPDATE vault_metadata SET schema_version = 1 WHERE singleton = 1")
    session.lock()

    reopened = VaultService(database_path).unlock(MASTER_PASSWORD)
    reopened_credentials = CredentialRepository(database_path, reopened)
    service = CategoryService(
        CategoryRepository(database_path, reopened),
        reopened_credentials,
    )

    assert [category.name for category in service.synchronize()] == ["Legado"]
    assert reopened_credentials.get(original.id) == original
    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT schema_version FROM vault_metadata WHERE singleton = 1"
        ).fetchone()[0]
    assert version == 2


def test_wrong_password_does_not_migrate_an_old_vault(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-locked.db"
    session = VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    session.lock()
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE categories")
        connection.execute("UPDATE vault_metadata SET schema_version = 1 WHERE singleton = 1")

    with pytest.raises(VaultUnlockError):
        VaultService(database_path).unlock("senha-incorreta-ficticia")

    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT schema_version FROM vault_metadata WHERE singleton = 1"
        ).fetchone()[0]
        category_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'categories'"
        ).fetchone()
    assert version == 1
    assert category_table is None
