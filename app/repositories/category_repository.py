"""Persistência autenticada e criptografada de categorias."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from app.database.connection import connect_database
from app.database.schema import initialize_schema
from app.models.category import Category
from app.models.credential import utc_now_iso
from app.security.session import VaultSession
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
            rows = connection.execute(
                """
                SELECT id, payload_nonce, payload_ciphertext
                FROM categories ORDER BY updated_at DESC, id ASC
                """
            ).fetchall()
        return [self._decrypt_row(row) for row in rows]

    def update(self, category: Category) -> Category:
        updated = replace(category, updated_at=utc_now_iso())
        encrypted = self._encrypt(updated)
        with connect_database(self._database_path) as connection:
            cursor = connection.execute(
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

    def delete(self, category_id: str) -> None:
        with connect_database(self._database_path) as connection:
            cursor = connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        if cursor.rowcount != 1:
            raise CategoryNotFoundError("Categoria não encontrada.")

    def _encrypt(self, category: Category) -> EncryptedData:
        payload = json.dumps(category.to_dict(), ensure_ascii=False, separators=(",", ":"))
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
        return f"senhas:category:v1:{self._session.vault_id}:{category_id}".encode("utf-8")
