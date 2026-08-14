"""Criptografia autenticada para os dados do cofre."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


AES_256_KEY_BYTES = 32
GCM_NONCE_BYTES = 12
GCM_TAG_BYTES = 16


class DecryptionError(ValueError):
    """Indica que um conteúdo não pôde ser autenticado e descriptografado."""


@dataclass(frozen=True, slots=True)
class EncryptedData:
    """Payload AES-GCM com nonce e tag anexada ao ciphertext."""

    nonce: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        if len(self.nonce) != GCM_NONCE_BYTES:
            raise ValueError(f"O nonce deve ter {GCM_NONCE_BYTES} bytes.")
        if len(self.ciphertext) < GCM_TAG_BYTES:
            raise ValueError("O ciphertext AES-GCM deve conter a tag de autenticação.")


class CryptoService:
    """Executa AES-256-GCM sem persistir a chave fornecida."""

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes):
            raise TypeError("A chave deve ser fornecida como bytes.")
        if len(key) != AES_256_KEY_BYTES:
            raise ValueError("AES-256 requer uma chave de exatamente 32 bytes.")

        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes, associated_data: bytes | None = None) -> EncryptedData:
        """Criptografa e autentica bytes usando um nonce aleatório novo."""
        if not isinstance(plaintext, bytes):
            raise TypeError("O plaintext deve ser fornecido como bytes.")
        self._validate_associated_data(associated_data)

        nonce = os.urandom(GCM_NONCE_BYTES)
        ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)
        return EncryptedData(nonce=nonce, ciphertext=ciphertext)

    def decrypt(self, encrypted: EncryptedData, associated_data: bytes | None = None) -> bytes:
        """Autentica o payload antes de devolver o plaintext."""
        if not isinstance(encrypted, EncryptedData):
            raise TypeError("O conteúdo deve ser um EncryptedData.")
        self._validate_associated_data(associated_data)

        try:
            return self._cipher.decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                associated_data,
            )
        except InvalidTag as exc:
            # A mensagem não revela se chave, nonce, AAD ou ciphertext estava errado.
            raise DecryptionError("Não foi possível autenticar o conteúdo criptografado.") from exc

    def encrypt_text(self, plaintext: str, associated_data: bytes | None = None) -> EncryptedData:
        """Codifica texto em UTF-8 e o criptografa."""
        if not isinstance(plaintext, str):
            raise TypeError("O plaintext deve ser fornecido como str.")
        return self.encrypt(plaintext.encode("utf-8"), associated_data)

    def decrypt_text(self, encrypted: EncryptedData, associated_data: bytes | None = None) -> str:
        """Descriptografa bytes autenticados e decodifica o texto UTF-8."""
        return self.decrypt(encrypted, associated_data).decode("utf-8")

    @staticmethod
    def _validate_associated_data(associated_data: bytes | None) -> None:
        if associated_data is not None and not isinstance(associated_data, bytes):
            raise TypeError("Os dados associados devem ser bytes ou None.")
