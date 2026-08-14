"""Metadados públicos necessários para derivar e validar a chave do cofre."""

from __future__ import annotations

from dataclasses import dataclass

from app.security.kdf import KDFParameters


@dataclass(frozen=True, slots=True)
class VaultMetadata:
    """Metadados não secretos de um cofre local."""

    vault_id: str
    format_version: int
    schema_version: int
    salt: bytes
    kdf_parameters: KDFParameters
    verifier_nonce: bytes
    verifier_ciphertext: bytes
    created_at: str
