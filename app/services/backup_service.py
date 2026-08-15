"""Backups consistentes do cofre já criptografado."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.repositories.credential_repository import (
    CredentialRepository,
    RepositoryIntegrityError,
)
from app.repositories.category_repository import (
    CategoryRepository,
    CategoryRepositoryIntegrityError,
)
from app.services.vault_service import (
    UnsupportedVaultError,
    VaultNotFoundError,
    VaultService,
    VaultUnlockError,
)


class BackupError(RuntimeError):
    """Indica que o snapshot não pôde ser criado ou validado."""


class BackupAuthenticationError(BackupError):
    """Evita distinguir senha incorreta de conteúdo adulterado."""


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

    @property
    def retention(self) -> int:
        return self._retention

    def set_retention(self, retention: int) -> None:
        if retention < 1:
            raise ValueError("A retenção deve preservar pelo menos um backup.")
        self._retention = retention

    def create_backup(self, now: datetime | None = None) -> Path:
        """Cria, valida e publica atomicamente um snapshot do cofre."""
        if not self._vault_path.is_file():
            raise BackupError("O arquivo do cofre não foi encontrado.")

        self._backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = (now or datetime.now(UTC)).astimezone(UTC)
        name = timestamp.strftime("vault_%Y-%m-%d_%H-%M-%S_%f.db")
        destination = self._backup_directory / name
        self._publish_snapshot(self._vault_path, destination)
        self._prune_old_backups()
        return destination

    def export_backup(self, destination: Path) -> Path:
        """Exporta uma cópia consistente do cofre para um destino escolhido."""
        selected = Path(destination)
        if not self._vault_path.is_file():
            raise BackupError("O arquivo do cofre não foi encontrado.")
        if self._same_path(selected, self._vault_path):
            raise BackupError("Escolha um destino diferente do cofre em uso.")
        self._publish_snapshot(self._vault_path, selected)
        return selected

    def restore_backup(self, source: Path, master_password: str) -> Path:
        """Valida e restaura um cofre, preservando antes o conteúdo atual."""
        selected = Path(source)
        if not selected.is_file() or self._same_path(selected, self._vault_path):
            raise BackupError("Selecione um arquivo de backup válido.")

        self._vault_path.parent.mkdir(parents=True, exist_ok=True)
        candidate = self._vault_path.with_name(
            f".{self._vault_path.name}.{uuid4().hex}.restore.tmp"
        )
        try:
            self._create_snapshot(selected, candidate)
            self._authenticate_vault_content(candidate, master_password)
            safety_backup = self.create_backup()
            candidate.chmod(0o600)
            os.replace(candidate, self._vault_path)
            return safety_backup
        except BackupAuthenticationError:
            raise
        except BackupError:
            raise
        except OSError as exc:
            raise BackupError("Não foi possível restaurar o cofre com segurança.") from exc
        finally:
            if candidate.exists():
                try:
                    candidate.unlink()
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

    def _publish_snapshot(self, source: Path, destination: Path) -> None:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            self._create_snapshot(source, temporary)
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        except BackupError:
            raise
        except OSError as exc:
            raise BackupError("Não foi possível criar um backup íntegro do cofre.") from exc
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    @staticmethod
    def _create_snapshot(source_path: Path, target_path: Path) -> None:
        source: sqlite3.Connection | None = None
        target: sqlite3.Connection | None = None
        try:
            source = sqlite3.connect(source_path)
            target = sqlite3.connect(target_path)
            source.backup(target)
            target.commit()
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            metadata = target.execute(
                "SELECT 1 FROM vault_metadata WHERE singleton = 1"
            ).fetchone()
            foreign_key_errors = target.execute("PRAGMA foreign_key_check").fetchone()
            if (
                integrity is None
                or integrity[0] != "ok"
                or metadata is None
                or foreign_key_errors is not None
            ):
                raise BackupError("O snapshot não passou na validação de integridade.")
        except BackupError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise BackupError("Não foi possível criar um backup íntegro do cofre.") from exc
        finally:
            # No Windows, commit não libera o handle: close deve ocorrer antes do replace.
            if target is not None:
                target.close()
            if source is not None:
                source.close()

    @staticmethod
    def _authenticate_vault_content(database_path: Path, master_password: str) -> None:
        session = None
        try:
            session = VaultService(database_path).unlock(master_password)
            CredentialRepository(database_path, session).list_all()
            CategoryRepository(database_path, session).list_all()
        except (
            CategoryRepositoryIntegrityError,
            RepositoryIntegrityError,
            UnsupportedVaultError,
            VaultNotFoundError,
            VaultUnlockError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise BackupAuthenticationError(
                "A senha está incorreta ou o arquivo não é um cofre íntegro."
            ) from exc
        finally:
            if session is not None:
                session.lock()

    @staticmethod
    def _same_path(first: Path, second: Path) -> bool:
        try:
            return first.resolve() == second.resolve()
        except OSError:
            return False
