"""Migração não destrutiva do armazenamento usado durante o desenvolvimento."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.backup_service import BackupError, BackupService


class StorageMigrationError(RuntimeError):
    """Indica que o cofre legado não pôde ser copiado com segurança."""


@dataclass(frozen=True, slots=True)
class StorageMigrationResult:
    vault_copied: bool = False
    backups_copied: int = 0
    backups_skipped: int = 0


def migrate_legacy_storage(
    legacy_vault_path: Path,
    legacy_backup_directory: Path,
    target_vault_path: Path,
    target_backup_directory: Path,
) -> StorageMigrationResult:
    """Copia uma instalação antiga somente quando o novo cofre ainda não existe."""
    legacy_vault = Path(legacy_vault_path)
    target_vault = Path(target_vault_path)
    if target_vault.exists() or not legacy_vault.is_file():
        return StorageMigrationResult()

    try:
        transfer = BackupService(legacy_vault, Path(legacy_backup_directory))
        transfer.export_backup(target_vault)
    except BackupError as exc:
        raise StorageMigrationError(
            "O cofre existente não pôde ser validado para a nova pasta."
        ) from exc

    copied = 0
    skipped = 0
    source_backups = Path(legacy_backup_directory)
    if source_backups.is_dir():
        for source in sorted(source_backups.glob("vault_*.db")):
            destination = Path(target_backup_directory) / source.name
            if destination.exists():
                continue
            try:
                BackupService(source, source_backups).export_backup(destination)
                copied += 1
            except BackupError:
                skipped += 1

    return StorageMigrationResult(
        vault_copied=True,
        backups_copied=copied,
        backups_skipped=skipped,
    )
