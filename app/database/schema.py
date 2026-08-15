"""Schema SQLite centralizado e versionado."""

from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vault_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    vault_id TEXT NOT NULL UNIQUE,
    format_version INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    salt BLOB NOT NULL,
    kdf_time_cost INTEGER NOT NULL,
    kdf_memory_cost_kib INTEGER NOT NULL,
    kdf_parallelism INTEGER NOT NULL,
    kdf_hash_length INTEGER NOT NULL,
    kdf_version INTEGER NOT NULL,
    verifier_nonce BLOB NOT NULL,
    verifier_ciphertext BLOB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credentials (
    id TEXT PRIMARY KEY,
    payload_nonce BLOB NOT NULL,
    payload_ciphertext BLOB NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_credentials_updated_at
    ON credentials(updated_at DESC);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    payload_nonce BLOB NOT NULL,
    payload_ciphertext BLOB NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_updated_at
    ON categories(updated_at DESC);
"""


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Cria o schema conhecido sem alterar cofres existentes."""
    connection.executescript(SCHEMA_SQL)
