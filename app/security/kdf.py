"""Derivação de chave de cofre com Argon2id."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw

SALT_BYTES = 16
AES_256_KEY_BYTES = 32
MAX_TIME_COST = 10
MAX_MEMORY_COST_KIB = 256 * 1_024
MAX_PARALLELISM = 16


@dataclass(frozen=True, slots=True)
class KDFParameters:
    """Parâmetros versionáveis do Argon2id, persistíveis como metadados."""

    time_cost: int = 3
    memory_cost_kib: int = 65_536
    parallelism: int = 4
    hash_length: int = AES_256_KEY_BYTES
    version: int = ARGON2_VERSION

    def __post_init__(self) -> None:
        if self.time_cost < 1:
            raise ValueError("time_cost deve ser positivo.")
        if self.time_cost > MAX_TIME_COST:
            raise ValueError("time_cost excede o limite seguro suportado.")
        if self.parallelism < 1:
            raise ValueError("parallelism deve ser positivo.")
        if self.parallelism > MAX_PARALLELISM:
            raise ValueError("parallelism excede o limite seguro suportado.")
        if self.memory_cost_kib < 8 * self.parallelism:
            raise ValueError("memory_cost_kib é insuficiente para o parallelism escolhido.")
        if self.memory_cost_kib > MAX_MEMORY_COST_KIB:
            raise ValueError("memory_cost_kib excede o limite seguro suportado.")
        if self.hash_length != AES_256_KEY_BYTES:
            raise ValueError("A chave derivada deve ter 32 bytes para AES-256.")


def generate_salt() -> bytes:
    """Gera um salt criptograficamente seguro para um novo cofre."""
    return secrets.token_bytes(SALT_BYTES)


def derive_key(
    master_password: str,
    salt: bytes,
    parameters: KDFParameters | None = None,
) -> bytes:
    """Deriva uma chave AES-256 sem armazenar a senha mestra."""
    if not isinstance(master_password, str):
        raise TypeError("A senha mestra deve ser fornecida como str.")
    if not master_password:
        raise ValueError("A senha mestra não pode ser vazia.")
    if not isinstance(salt, bytes):
        raise TypeError("O salt deve ser fornecido como bytes.")
    if len(salt) < SALT_BYTES:
        raise ValueError(f"O salt deve ter pelo menos {SALT_BYTES} bytes.")

    selected = parameters or KDFParameters()
    return hash_secret_raw(
        secret=master_password.encode("utf-8"),
        salt=salt,
        time_cost=selected.time_cost,
        memory_cost=selected.memory_cost_kib,
        parallelism=selected.parallelism,
        hash_len=selected.hash_length,
        type=Type.ID,
        version=selected.version,
    )
