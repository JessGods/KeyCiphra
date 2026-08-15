"""Preferências não sensíveis e limites seguros do aplicativo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MIN_AUTO_LOCK_MINUTES = 1
MAX_AUTO_LOCK_MINUTES = 60
MIN_CLIPBOARD_SECONDS = 10
MAX_CLIPBOARD_SECONDS = 120
MIN_BACKUP_RETENTION = 1
MAX_BACKUP_RETENTION = 50


@dataclass(frozen=True, slots=True)
class AppSettings:
    auto_lock_minutes: int = 5
    clipboard_seconds: int = 25
    backup_retention: int = 10

    def __post_init__(self) -> None:
        self._validate_integer("auto_lock_minutes", self.auto_lock_minutes)
        self._validate_integer("clipboard_seconds", self.clipboard_seconds)
        self._validate_integer("backup_retention", self.backup_retention)
        if not MIN_AUTO_LOCK_MINUTES <= self.auto_lock_minutes <= MAX_AUTO_LOCK_MINUTES:
            raise ValueError("Tempo de bloqueio automático fora do intervalo permitido.")
        if not MIN_CLIPBOARD_SECONDS <= self.clipboard_seconds <= MAX_CLIPBOARD_SECONDS:
            raise ValueError("Tempo de clipboard fora do intervalo permitido.")
        if not MIN_BACKUP_RETENTION <= self.backup_retention <= MAX_BACKUP_RETENTION:
            raise ValueError("Retenção de backups fora do intervalo permitido.")

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AppSettings:
        expected = {"auto_lock_minutes", "clipboard_seconds", "backup_retention"}
        if set(values) != expected:
            raise ValueError("Arquivo de configurações incompatível.")
        return cls(
            auto_lock_minutes=values["auto_lock_minutes"],
            clipboard_seconds=values["clipboard_seconds"],
            backup_retention=values["backup_retention"],
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @staticmethod
    def _validate_integer(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} deve ser um número inteiro.")
