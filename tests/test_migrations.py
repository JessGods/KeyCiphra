"""Testes da cadeia transacional de migrações do schema."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from app.database.migrations import SchemaMigrationError, migrate_schema


def _legacy_connection(*, include_metadata: bool = True) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE vault_metadata (
            singleton INTEGER PRIMARY KEY,
            schema_version INTEGER NOT NULL
        )
        """
    )
    if include_metadata:
        connection.execute(
            "INSERT INTO vault_metadata (singleton, schema_version) VALUES (1, 1)"
        )
    connection.commit()
    return connection


def test_schema_migrates_incrementally_from_v1_to_v2() -> None:
    with closing(_legacy_connection()) as connection, connection:
        migrate_schema(connection, 1)
        version = connection.execute(
            "SELECT schema_version FROM vault_metadata WHERE singleton = 1"
        ).fetchone()[0]
        category_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'categories'"
        ).fetchone()

        assert version == 2
        assert category_table is not None


def test_failed_migration_rolls_back_ddl_and_metadata() -> None:
    with closing(_legacy_connection(include_metadata=False)) as connection:
        with pytest.raises(SchemaMigrationError), connection:
            migrate_schema(connection, 1)

        category_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'categories'"
        ).fetchone()
        assert category_table is None


@pytest.mark.parametrize("version", [0, 3])
def test_unsupported_schema_versions_are_rejected(version: int) -> None:
    with closing(_legacy_connection()) as connection:
        with pytest.raises(SchemaMigrationError):
            migrate_schema(connection, version)
