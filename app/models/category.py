"""Categoria criptografada usada para organizar credenciais."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4

from app.models.credential import utc_now_iso


@dataclass(frozen=True, slots=True)
class Category:
    """Nome e identidade de uma categoria armazenados dentro de payload autenticado."""

    id: str
    name: str
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, name: str) -> Category:
        now = utc_now_iso()
        return cls(id=str(uuid4()), name=name, created_at=now, updated_at=now)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Category:
        expected = {"id", "name", "created_at", "updated_at"}
        if set(data) != expected or not all(isinstance(data[field], str) for field in expected):
            raise ValueError("O payload da categoria possui formato inválido.")
        return cls(**{field: data[field] for field in expected})  # type: ignore[arg-type]
