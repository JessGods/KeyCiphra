"""Migrações incrementais e transacionais do schema do cofre."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.database.schema import SCHEMA_VERSION

OLDEST_SUPPORTED_SCHEMA_VERSION = 1


class SchemaMigrationError(RuntimeError):
    """Indica uma cadeia de migração ausente ou inconsistente."""


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            payload_nonce BLOB NOT NULL,
            payload_ciphertext BLOB NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_categories_updated_at
        ON categories(updated_at DESC)
        """
    )


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migrate_v1_to_v2,
}


def migrate_schema(
    connection: sqlite3.Connection,
    current_version: int,
    target_version: int = SCHEMA_VERSION,
) -> None:
    """Avança cada versão uma vez e atualiza os metadados na mesma transação."""
    if current_version < OLDEST_SUPPORTED_SCHEMA_VERSION or current_version > target_version:
        raise SchemaMigrationError("Versão de schema incompatível com esta aplicação.")

    savepoint = "keyciphra_schema_migration"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        version = current_version
        while version < target_version:
            migration = MIGRATIONS.get(version)
            if migration is None:
                raise SchemaMigrationError(f"Migração ausente para o schema {version}.")
            migration(connection)
            next_version = version + 1
            cursor = connection.execute(
                """
                UPDATE vault_metadata
                SET schema_version = ?
                WHERE singleton = 1 AND schema_version = ?
                """,
                (next_version, version),
            )
            if cursor.rowcount != 1:
                raise SchemaMigrationError("Os metadados mudaram durante a migração.")
            version = next_version
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise
    else:
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
