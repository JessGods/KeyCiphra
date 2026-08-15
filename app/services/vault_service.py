"""Criação, detecção e desbloqueio do cofre local."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.database.connection import connect_database
from app.database.migrations import (
    OLDEST_SUPPORTED_SCHEMA_VERSION,
    SchemaMigrationError,
    migrate_schema,
)
from app.database.schema import SCHEMA_VERSION, initialize_schema
from app.models.vault_metadata import VaultMetadata
from app.security.kdf import KDFParameters, derive_key, generate_salt
from app.security.session import VaultSession
from app.services.crypto_service import CryptoService, DecryptionError, EncryptedData

FORMAT_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = frozenset(range(OLDEST_SUPPORTED_SCHEMA_VERSION, SCHEMA_VERSION + 1))
MINIMUM_MASTER_PASSWORD_LENGTH = 12
VERIFIER_PLAINTEXT = b"senhas-vault-unlock-verifier-v1"


class VaultAlreadyExistsError(RuntimeError):
    """Indica tentativa de sobrescrever um cofre existente."""


class VaultNotFoundError(FileNotFoundError):
    """Indica ausência de um cofre inicializado."""


class VaultUnlockError(ValueError):
    """Falha genérica de desbloqueio, sem detalhes criptográficos."""


class UnsupportedVaultError(RuntimeError):
    """Indica formato ou schema incompatível com esta versão."""


class VaultService:
    """Orquestra operações do cofre sem expor a senha mestra."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def exists(self) -> bool:
        if not self.database_path.is_file():
            return False
        try:
            with connect_database(self.database_path) as connection:
                table = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'vault_metadata'
                    """
                ).fetchone()
                if table is None:
                    return False
                return connection.execute(
                    "SELECT 1 FROM vault_metadata WHERE singleton = 1"
                ).fetchone() is not None
        except sqlite3.DatabaseError:
            return False

    def create(
        self,
        master_password: str,
        parameters: KDFParameters | None = None,
    ) -> VaultSession:
        """Cria um cofre novo sem persistir senha mestra ou chave."""
        self._validate_new_master_password(master_password)
        selected = parameters or KDFParameters()

        with connect_database(self.database_path) as connection:
            initialize_schema(connection)
            if connection.execute("SELECT 1 FROM vault_metadata").fetchone() is not None:
                raise VaultAlreadyExistsError("Já existe um cofre neste caminho.")

            vault_id = str(uuid4())
            salt = generate_salt()
            key = derive_key(master_password, salt, selected)
            crypto = CryptoService(key)
            verifier = crypto.encrypt(VERIFIER_PLAINTEXT, self._verifier_aad(vault_id))
            connection.execute(
                """
                INSERT INTO vault_metadata (
                    singleton, vault_id, format_version, schema_version, salt,
                    kdf_time_cost, kdf_memory_cost_kib, kdf_parallelism,
                    kdf_hash_length, kdf_version, verifier_nonce,
                    verifier_ciphertext, created_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vault_id,
                    FORMAT_VERSION,
                    SCHEMA_VERSION,
                    salt,
                    selected.time_cost,
                    selected.memory_cost_kib,
                    selected.parallelism,
                    selected.hash_length,
                    selected.version,
                    verifier.nonce,
                    verifier.ciphertext,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return VaultSession(vault_id, key)

    def unlock(self, master_password: str) -> VaultSession:
        """Deriva a chave e valida um valor autenticado conhecido."""
        metadata = self._load_metadata()
        self._validate_supported_versions(metadata)
        try:
            key = derive_key(master_password, metadata.salt, metadata.kdf_parameters)
            plaintext = CryptoService(key).decrypt(
                EncryptedData(metadata.verifier_nonce, metadata.verifier_ciphertext),
                self._verifier_aad(metadata.vault_id),
            )
            if plaintext != VERIFIER_PLAINTEXT:
                raise VaultUnlockError("Não foi possível desbloquear o cofre.")
        except (DecryptionError, TypeError, ValueError) as exc:
            raise VaultUnlockError("Não foi possível desbloquear o cofre.") from exc
        self._migrate_schema(metadata.schema_version)
        return VaultSession(metadata.vault_id, key)

    def _load_metadata(self) -> VaultMetadata:
        if not self.database_path.is_file():
            raise VaultNotFoundError("Cofre não encontrado.")
        try:
            with connect_database(self.database_path) as connection:
                row = connection.execute(
                    "SELECT * FROM vault_metadata WHERE singleton = 1"
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise VaultNotFoundError("Cofre não encontrado ou inválido.") from exc
        if row is None:
            raise VaultNotFoundError("Cofre não encontrado.")
        try:
            parameters = KDFParameters(
                time_cost=int(row["kdf_time_cost"]),
                memory_cost_kib=int(row["kdf_memory_cost_kib"]),
                parallelism=int(row["kdf_parallelism"]),
                hash_length=int(row["kdf_hash_length"]),
                version=int(row["kdf_version"]),
            )
            return VaultMetadata(
                vault_id=str(row["vault_id"]),
                format_version=int(row["format_version"]),
                schema_version=int(row["schema_version"]),
                salt=bytes(row["salt"]),
                kdf_parameters=parameters,
                verifier_nonce=bytes(row["verifier_nonce"]),
                verifier_ciphertext=bytes(row["verifier_ciphertext"]),
                created_at=str(row["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VaultUnlockError("Não foi possível desbloquear o cofre.") from exc

    @staticmethod
    def _validate_new_master_password(master_password: str) -> None:
        if not isinstance(master_password, str):
            raise TypeError("A senha mestra deve ser fornecida como str.")
        if len(master_password) < MINIMUM_MASTER_PASSWORD_LENGTH:
            raise ValueError(
                f"Use uma frase-senha com pelo menos {MINIMUM_MASTER_PASSWORD_LENGTH} caracteres."
            )

    @staticmethod
    def _validate_supported_versions(metadata: VaultMetadata) -> None:
        if (
            metadata.format_version != FORMAT_VERSION
            or metadata.schema_version not in SUPPORTED_SCHEMA_VERSIONS
        ):
            raise UnsupportedVaultError("A versão deste cofre não é suportada.")

    def _migrate_schema(self, current_version: int) -> None:
        """Aplica migrações aditivas somente após autenticar a senha mestra."""
        if current_version == SCHEMA_VERSION:
            return
        try:
            with connect_database(self.database_path) as connection:
                migrate_schema(connection, current_version)
        except (SchemaMigrationError, sqlite3.DatabaseError) as exc:
            raise UnsupportedVaultError("Não foi possível atualizar o schema do cofre.") from exc

    @staticmethod
    def _verifier_aad(vault_id: str) -> bytes:
        return f"senhas:vault-verifier:v1:{vault_id}".encode()
