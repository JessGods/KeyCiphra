"""Entidade de credencial armazenada no cofre."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4


def utc_now_iso() -> str:
    """Retorna um timestamp UTC estável e adequado para persistência."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Credential:
    """Dados sensíveis de uma credencial; todos os campos são criptografados."""

    id: str
    title: str
    username: str
    password: str
    url: str
    category: str
    notes: str
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        title: str,
        username: str = "",
        password: str = "",
        url: str = "",
        category: str = "",
        notes: str = "",
    ) -> Credential:
        """Cria uma credencial nova com ID aleatório e timestamps UTC."""
        now = utc_now_iso()
        return cls(
            id=str(uuid4()),
            title=title,
            username=username,
            password=password,
            url=url,
            category=category,
            notes=notes,
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, str]:
        """Converte a entidade para serialização dentro do payload criptografado."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Credential:
        """Reconstrói uma credencial e rejeita payloads inesperados."""
        expected = {
            "id",
            "title",
            "username",
            "password",
            "url",
            "category",
            "notes",
            "created_at",
            "updated_at",
        }
        if set(data) != expected or not all(isinstance(data[field], str) for field in expected):
            raise ValueError("O payload da credencial possui formato inválido.")
        return cls(**{field: data[field] for field in expected})  # type: ignore[arg-type]
