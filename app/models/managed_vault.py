"""Metadados não secretos necessários para selecionar um cofre bloqueado."""

from __future__ import annotations

from dataclasses import asdict, dataclass

LEGACY_STORAGE = "legacy"
MANAGED_STORAGE = "managed"
SUPPORTED_STORAGE_KINDS = frozenset({LEGACY_STORAGE, MANAGED_STORAGE})


@dataclass(frozen=True, slots=True)
class ManagedVault:
    id: str
    name: str
    storage_kind: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: object) -> ManagedVault:
        if not isinstance(values, dict):
            raise ValueError("O registro do cofre deve ser um objeto.")
        expected = {"id", "name", "storage_kind", "created_at"}
        if set(values) != expected or not all(
            isinstance(values[key], str) for key in expected
        ):
            raise ValueError("O registro do cofre é inválido.")
        return cls(
            id=values["id"],
            name=values["name"],
            storage_kind=values["storage_kind"],
            created_at=values["created_at"],
        )
