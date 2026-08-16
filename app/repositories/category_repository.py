"""Persistência autenticada e criptografada de categorias."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from app.database.connection import connect_database
from app.database.schema import initialize_schema
from app.models.category import Category
from app.models.credential import utc_now_iso
from app.security.session import VaultSession
from app.security.storage_limits import MAX_CATEGORIES, MAX_CATEGORY_CIPHERTEXT_BYTES
from app.services.crypto_service import DecryptionError, EncryptedData


class CategoryNotFoundError(LookupError):
    """Indica que uma categoria não existe."""


class CategoryRepositoryIntegrityError(RuntimeError):
    """Indica conteúdo de categoria inválido ou adulterado."""


class CategoryRepository:
    """Armazena categorias sem revelar seus nomes no SQLite."""

    def __init__(self, database_path: Path, session: VaultSession) -> None:
        self._database_path = Path(database_path)
        self._session = session
        with connect_database(self._database_path) as connection:
            initialize_schema(connection)

    def add(self, category: Category) -> Category:
        encrypted = self._encrypt(category)
        try:
            with connect_database(self._database_path) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM categories LIMIT ?)",
                    (MAX_CATEGORIES,),
                ).fetchone()[0]
                if count >= MAX_CATEGORIES:
                    raise ValueError(
                        f"O cofre atingiu o limite de {MAX_CATEGORIES} categorias."
                    )
                connection.execute(
                    """
                    INSERT INTO categories (
                        id, payload_nonce, payload_ciphertext, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        category.id,
                        encrypted.nonce,
                        encrypted.ciphertext,
                        category.created_at,
                        category.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Já existe uma categoria com este ID.") from exc
        return category

    def get(self, category_id: str) -> Category:
        with connect_database(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT id, payload_nonce, payload_ciphertext
                FROM categories WHERE id = ?
                """,
                (category_id,),
            ).fetchone()
        if row is None:
            raise CategoryNotFoundError("Categoria não encontrada.")
        return self._decrypt_row(row)

    def list_all(self) -> list[Category]:
        with connect_database(self._database_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM categories LIMIT ?)",
                (MAX_CATEGORIES + 1,),
            ).fetchone()[0]
            largest = connection.execute(
                "SELECT COALESCE(MAX(length(payload_ciphertext)), 0) FROM categories"
            ).fetchone()[0]
            if count > MAX_CATEGORIES or largest > MAX_CATEGORY_CIPHERTEXT_BYTES:
                raise CategoryRepositoryIntegrityError(
                    "O cofre excede os limites defensivos de categorias."
                )
            rows = connection.execute(
                """
                SELECT id, payload_nonce, payload_ciphertext
                FROM categories ORDER BY updated_at DESC, id ASC
                """
            ).fetchall()
        return [self._decrypt_row(row) for row in rows]

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Compartilha uma transação com operações de credenciais relacionadas."""
        with connect_database(self._database_path) as connection:
            yield connection

    def update(
        self,
        category: Category,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> Category:
        updated = replace(category, updated_at=utc_now_iso())
        encrypted = self._encrypt(updated)
        if connection is not None:
            cursor = connection.execute(
                """
                UPDATE categories
                SET payload_nonce = ?, payload_ciphertext = ?, updated_at = ?
                WHERE id = ?
                """,
                (encrypted.nonce, encrypted.ciphertext, updated.updated_at, updated.id),
            )
        else:
            with connect_database(self._database_path) as local_connection:
                cursor = local_connection.execute(
                    """
                    UPDATE categories
                    SET payload_nonce = ?, payload_ciphertext = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (encrypted.nonce, encrypted.ciphertext, updated.updated_at, updated.id),
                )
        if cursor.rowcount != 1:
            raise CategoryNotFoundError("Categoria não encontrada.")
        return updated

    def delete(
        self,
        category_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is not None:
            cursor = connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        else:
            with connect_database(self._database_path) as local_connection:
                cursor = local_connection.execute(
                    "DELETE FROM categories WHERE id = ?", (category_id,)
                )
        if cursor.rowcount != 1:
            raise CategoryNotFoundError("Categoria não encontrada.")

    def _encrypt(self, category: Category) -> EncryptedData:
        payload = json.dumps(category.to_dict(), ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_CATEGORY_CIPHERTEXT_BYTES - 16:
            raise ValueError("A categoria excede o limite de 64 KiB.")
        return self._session.crypto.encrypt_text(payload, self._aad(category.id))

    def _decrypt_row(self, row: sqlite3.Row) -> Category:
        category_id = str(row["id"])
        try:
            payload = self._session.crypto.decrypt_text(
                EncryptedData(bytes(row["payload_nonce"]), bytes(row["payload_ciphertext"])),
                self._aad(category_id),
            )
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("Payload não é um objeto.")
            category = Category.from_dict(data)
            if category.id != category_id:
                raise ValueError("ID interno divergente.")
            return category
        except (DecryptionError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CategoryRepositoryIntegrityError(
                "Não foi possível autenticar uma categoria armazenada."
            ) from exc

    def _aad(self, category_id: str) -> bytes:
        return f"senhas:category:v1:{self._session.vault_id}:{category_id}".encode()
