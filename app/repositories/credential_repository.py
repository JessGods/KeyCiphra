"""Repository de credenciais com criptografia antes do SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from app.database.connection import connect_database
from app.models.credential import Credential, utc_now_iso
from app.security.session import VaultSession
from app.security.storage_limits import (
    MAX_CREDENTIAL_CIPHERTEXT_BYTES,
    MAX_CREDENTIALS,
)
from app.services.crypto_service import DecryptionError, EncryptedData


class CredentialNotFoundError(LookupError):
    """Indica que uma credencial não existe."""


class RepositoryIntegrityError(RuntimeError):
    """Indica conteúdo persistido inválido ou adulterado."""


class CredentialRepository:
    """Persiste somente payloads autenticados e criptografados."""

    def __init__(self, database_path: Path, session: VaultSession) -> None:
        self._database_path = Path(database_path)
        self._session = session

    def add(self, credential: Credential) -> Credential:
        encrypted = self._encrypt(credential)
        try:
            with connect_database(self._database_path) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM credentials LIMIT ?)",
                    (MAX_CREDENTIALS,),
                ).fetchone()[0]
                if count >= MAX_CREDENTIALS:
                    raise ValueError(
                        f"O cofre atingiu o limite de {MAX_CREDENTIALS} credenciais."
                    )
                connection.execute(
                    """
                    INSERT INTO credentials (
                        id, payload_nonce, payload_ciphertext, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        credential.id,
                        encrypted.nonce,
                        encrypted.ciphertext,
                        credential.created_at,
                        credential.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Já existe uma credencial com este ID.") from exc
        return credential

    def get(self, credential_id: str) -> Credential:
        with connect_database(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT id, payload_nonce, payload_ciphertext
                FROM credentials WHERE id = ?
                """,
                (credential_id,),
            ).fetchone()
        if row is None:
            raise CredentialNotFoundError("Credencial não encontrada.")
        return self._decrypt_row(row)

    def list_all(self) -> list[Credential]:
        with connect_database(self._database_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM credentials LIMIT ?)",
                (MAX_CREDENTIALS + 1,),
            ).fetchone()[0]
            largest = connection.execute(
                "SELECT COALESCE(MAX(length(payload_ciphertext)), 0) FROM credentials"
            ).fetchone()[0]
            if count > MAX_CREDENTIALS or largest > MAX_CREDENTIAL_CIPHERTEXT_BYTES:
                raise RepositoryIntegrityError(
                    "O cofre excede os limites defensivos de credenciais."
                )
            rows = connection.execute(
                """
                SELECT id, payload_nonce, payload_ciphertext
                FROM credentials ORDER BY updated_at DESC, id ASC
                """
            ).fetchall()
        return [self._decrypt_row(row) for row in rows]

    def update(self, credential: Credential) -> Credential:
        updated = replace(credential, updated_at=utc_now_iso())
        encrypted = self._encrypt(updated)
        with connect_database(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE credentials
                SET payload_nonce = ?, payload_ciphertext = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    encrypted.nonce,
                    encrypted.ciphertext,
                    updated.updated_at,
                    updated.id,
                ),
            )
        if cursor.rowcount != 1:
            raise CredentialNotFoundError("Credencial não encontrada.")
        return updated

    def delete(self, credential_id: str) -> None:
        with connect_database(self._database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM credentials WHERE id = ?",
                (credential_id,),
            )
        if cursor.rowcount != 1:
            raise CredentialNotFoundError("Credencial não encontrada.")

    def replace_category(
        self,
        old_name: str,
        new_name: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        """Reclassifica em uma transação todos os payloads de uma categoria."""
        old_key = old_name.strip().casefold()
        replacements: list[tuple[bytes, bytes, str, str]] = []
        for credential in self.list_all():
            if credential.category.strip().casefold() != old_key:
                continue
            updated = replace(credential, category=new_name, updated_at=utc_now_iso())
            encrypted = self._encrypt(updated)
            replacements.append(
                (encrypted.nonce, encrypted.ciphertext, updated.updated_at, updated.id)
            )
        if not replacements:
            return 0
        if connection is not None:
            connection.executemany(
                """
                UPDATE credentials
                SET payload_nonce = ?, payload_ciphertext = ?, updated_at = ?
                WHERE id = ?
                """,
                replacements,
            )
        else:
            with connect_database(self._database_path) as local_connection:
                local_connection.executemany(
                    """
                    UPDATE credentials
                    SET payload_nonce = ?, payload_ciphertext = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    replacements,
                )
        return len(replacements)

    def _encrypt(self, credential: Credential) -> EncryptedData:
        payload = json.dumps(
            credential.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(payload.encode("utf-8")) > MAX_CREDENTIAL_CIPHERTEXT_BYTES - 16:
            raise ValueError("A credencial excede o limite de 1 MiB.")
        return self._session.crypto.encrypt_text(payload, self._aad(credential.id))

    def _decrypt_row(self, row: sqlite3.Row) -> Credential:
        credential_id = str(row["id"])
        try:
            payload = self._session.crypto.decrypt_text(
                EncryptedData(bytes(row["payload_nonce"]), bytes(row["payload_ciphertext"])),
                self._aad(credential_id),
            )
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("Payload não é um objeto.")
            credential = Credential.from_dict(data)
            if credential.id != credential_id:
                raise ValueError("ID interno divergente.")
            return credential
        except (DecryptionError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise RepositoryIntegrityError(
                "Não foi possível autenticar uma credencial armazenada."
            ) from exc

    def _aad(self, credential_id: str) -> bytes:
        return f"senhas:credential:v1:{self._session.vault_id}:{credential_id}".encode()
