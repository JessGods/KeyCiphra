"""Backups consistentes do cofre já criptografado."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


class BackupError(RuntimeError):
    """Indica que o snapshot não pôde ser criado ou validado."""


class BackupService:
    """Cria snapshots SQLite atômicos e remove somente backups excedentes."""

    def __init__(
        self,
        vault_path: Path,
        backup_directory: Path,
        *,
        retention: int = 10,
    ) -> None:
        if retention < 1:
            raise ValueError("A retenção deve preservar pelo menos um backup.")
        self._vault_path = Path(vault_path)
        self._backup_directory = Path(backup_directory)
        self._retention = retention

    def create_backup(self, now: datetime | None = None) -> Path:
        """Cria, valida e publica atomicamente um snapshot do cofre."""
        if not self._vault_path.is_file():
            raise BackupError("O arquivo do cofre não foi encontrado.")

        self._backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        name = timestamp.strftime("vault_%Y-%m-%d_%H-%M-%S_%f.db")
        destination = self._backup_directory / name
        temporary = destination.with_suffix(".db.tmp")
        source: sqlite3.Connection | None = None
        target: sqlite3.Connection | None = None

        try:
            source = sqlite3.connect(self._vault_path)
            target = sqlite3.connect(temporary)
            source.backup(target)
            target.commit()
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            metadata = target.execute(
                "SELECT 1 FROM vault_metadata WHERE singleton = 1"
            ).fetchone()
            if integrity is None or integrity[0] != "ok" or metadata is None:
                raise BackupError("O snapshot não passou na validação de integridade.")

            # No Windows, commit não libera o handle: close deve ocorrer antes do replace.
            target.close()
            target = None
            source.close()
            source = None
            os.replace(temporary, destination)
            destination.chmod(0o600)
            self._prune_old_backups()
            return destination
        except (OSError, sqlite3.DatabaseError) as exc:
            raise BackupError("Não foi possível criar um backup íntegro do cofre.") from exc
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    def create_if_due(
        self,
        *,
        minimum_interval: timedelta = timedelta(hours=24),
        now: datetime | None = None,
    ) -> Path | None:
        """Cria backup somente quando o último snapshot já está antigo."""
        current = (now or datetime.now(UTC)).astimezone(UTC)
        backups = self.list_backups()
        if backups:
            newest = datetime.fromtimestamp(backups[0].stat().st_mtime, UTC)
            if current - newest < minimum_interval:
                return None
        return self.create_backup(current)

    def list_backups(self) -> list[Path]:
        if not self._backup_directory.is_dir():
            return []
        return sorted(
            self._backup_directory.glob("vault_*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _prune_old_backups(self) -> None:
        directory = self._backup_directory.resolve()
        for expired in self.list_backups()[self._retention :]:
            resolved = expired.resolve()
            if resolved.parent != directory:
                raise BackupError("Destino de retenção inválido.")
            resolved.unlink()
