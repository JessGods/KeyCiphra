"""Criação e configuração de conexões SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect_database(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Abre, transaciona e sempre fecha uma conexão configurada."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5.0)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
    finally:
        connection.close()
