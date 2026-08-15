"""Catálogo atômico e caminhos isolados para múltiplos cofres."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.models.archived_vault import ArchivedVault
from app.models.managed_vault import (
    LEGACY_STORAGE,
    MANAGED_STORAGE,
    SUPPORTED_STORAGE_KINDS,
    ManagedVault,
)
from app.security.kdf import KDFParameters
from app.security.session import VaultSession
from app.services.vault_service import VaultService

CATALOG_VERSION = 1
ARCHIVE_MANIFEST_VERSION = 1
ARCHIVE_MANIFEST_NAME = "manifest.json"
MAXIMUM_VAULT_NAME_LENGTH = 48


class VaultCatalogError(RuntimeError):
    """Indica catálogo inválido ou uma alteração que não pôde ser persistida."""


class VaultNameError(ValueError):
    """Indica nome vazio, duplicado ou inadequado para exibição."""


class VaultArchiveAuthenticationError(VaultCatalogError):
    """Evita arquivar um cofre sem confirmar sua senha mestra."""


class VaultRestoreAuthenticationError(VaultCatalogError):
    """Evita restaurar um arquivo sem confirmar sua senha mestra."""


class VaultCatalogService:
    """Registra cofres sem persistir senha mestra, chave ou caminho arbitrário."""

    def __init__(
        self,
        catalog_path: Path,
        managed_directory: Path,
        archived_directory: Path,
        legacy_vault_path: Path,
        legacy_backup_directory: Path,
    ) -> None:
        self._catalog_path = Path(catalog_path)
        self._managed_directory = Path(managed_directory)
        self._archived_directory = Path(archived_directory)
        self._legacy_vault_path = Path(legacy_vault_path)
        self._legacy_backup_directory = Path(legacy_backup_directory)
        self._vaults: list[ManagedVault] | None = None

    def initialize(self) -> tuple[ManagedVault, ...]:
        """Carrega o catálogo ou registra o cofre histórico sem movê-lo."""
        if self._vaults is not None:
            return tuple(self._vaults)
        if self._catalog_path.is_file():
            self._vaults = self._load()
            return tuple(self._vaults)

        vaults: list[ManagedVault] = []
        if VaultService(self._legacy_vault_path).exists():
            vaults.append(
                ManagedVault(
                    id=str(uuid4()),
                    name="Cofre principal",
                    storage_kind=LEGACY_STORAGE,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
        self._save(vaults)
        self._vaults = vaults
        return tuple(vaults)

    def list_vaults(self) -> tuple[ManagedVault, ...]:
        return self.initialize()

    def get(self, vault_id: str) -> ManagedVault:
        for vault in self.initialize():
            if vault.id == vault_id:
                return vault
        raise VaultCatalogError("O cofre selecionado não está mais disponível.")

    def create(
        self,
        name: str,
        master_password: str,
        parameters: KDFParameters | None = None,
    ) -> tuple[ManagedVault, VaultSession]:
        """Cria o arquivo primeiro e publica o registro somente após sucesso."""
        clean_name = self._validate_name(name)
        self._reject_duplicate_name(clean_name)
        vault_id = str(uuid4())
        vault = ManagedVault(
            id=vault_id,
            name=clean_name,
            storage_kind=MANAGED_STORAGE,
            created_at=datetime.now(UTC).isoformat(),
        )
        database_path = self.vault_path(vault)
        session: VaultSession | None = None
        try:
            session = VaultService(database_path).create(master_password, parameters)
            self._managed_directory.chmod(0o700)
            database_path.parent.chmod(0o700)
            database_path.chmod(0o600)
            updated = [*self.initialize(), vault]
            self._save(updated)
        except Exception:
            if session is not None:
                session.lock()
            self._remove_new_vault_files(database_path)
            raise
        self._vaults = updated
        return vault, session

    def rename(self, vault_id: str, name: str) -> ManagedVault:
        current = self.get(vault_id)
        clean_name = self._validate_name(name)
        self._reject_duplicate_name(clean_name, excluding_id=vault_id)
        renamed = ManagedVault(
            id=current.id,
            name=clean_name,
            storage_kind=current.storage_kind,
            created_at=current.created_at,
        )
        updated = [renamed if item.id == vault_id else item for item in self.initialize()]
        self._save(updated)
        self._vaults = updated
        return renamed

    def archive(self, vault_id: str, master_password: str) -> Path:
        """Remove da seleção e move os dados para uma pasta local recuperável."""
        vault = self.get(vault_id)
        database_path = self.vault_path(vault)
        session = None
        try:
            session = VaultService(database_path).unlock(master_password)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise VaultArchiveAuthenticationError(
                "Não foi possível autenticar o cofre para arquivamento."
            ) from exc
        finally:
            if session is not None:
                session.lock()

        archived_at = datetime.now(UTC)
        archive_path = self._archived_directory / (
            f"{archived_at.strftime('%Y%m%dT%H%M%S%fZ')}_{vault.id}"
        )
        moved: list[tuple[Path, Path]] = []
        try:
            archive_path.mkdir(parents=True, exist_ok=False)
            self._archived_directory.chmod(0o700)
            archive_path.chmod(0o700)
            self._write_json_atomic(
                archive_path / ARCHIVE_MANIFEST_NAME,
                {
                    "version": ARCHIVE_MANIFEST_VERSION,
                    "archived_at": archived_at.isoformat(),
                    "vault": vault.to_dict(),
                },
            )
            if vault.storage_kind == MANAGED_STORAGE:
                source_directory = database_path.parent
                destination = archive_path / "storage"
                os.replace(source_directory, destination)
                moved.append((destination, source_directory))
            else:
                destination = archive_path / "vault.db"
                os.replace(database_path, destination)
                moved.append((destination, database_path))
                backup_directory = self.backup_directory(vault)
                if backup_directory.is_dir():
                    archived_backups = archive_path / "backups"
                    os.replace(backup_directory, archived_backups)
                    moved.append((archived_backups, backup_directory))

            updated = [item for item in self.initialize() if item.id != vault.id]
            self._save(updated)
        except (OSError, VaultCatalogError) as exc:
            for source, destination in reversed(moved):
                if source.exists() and not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
            try:
                (archive_path / ARCHIVE_MANIFEST_NAME).unlink(missing_ok=True)
            except OSError:
                pass
            try:
                archive_path.rmdir()
            except OSError:
                pass
            raise VaultCatalogError("Não foi possível arquivar o cofre com segurança.") from exc
        self._vaults = updated
        return archive_path

    def list_archived(self) -> tuple[ArchivedVault, ...]:
        """Lista apenas estruturas reconhecidas dentro da pasta de arquivos."""
        if not self._archived_directory.is_dir():
            return ()
        archives: list[ArchivedVault] = []
        for directory in self._archived_directory.iterdir():
            try:
                archived = self._load_archived(directory)
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                continue
            if archived is not None:
                archives.append(archived)
        return tuple(sorted(archives, key=lambda item: item.archived_at, reverse=True))

    def get_archived(self, archive_key: str) -> ArchivedVault:
        self._validate_archive_key(archive_key)
        for archived in self.list_archived():
            if archived.archive_key == archive_key:
                return archived
        raise VaultCatalogError("O cofre arquivado não está mais disponível.")

    def restore_archived(
        self,
        archive_key: str,
        name: str,
        master_password: str,
    ) -> ManagedVault:
        """Autentica e devolve o arquivo ao catálogo sem substituir outro cofre."""
        archived = self.get_archived(archive_key)
        clean_name = self._validate_name(name)
        self._reject_duplicate_name(clean_name)
        source_database = self._archived_database_path(archived)
        session = None
        try:
            session = VaultService(source_database).unlock(master_password)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise VaultRestoreAuthenticationError(
                "Não foi possível autenticar o cofre arquivado."
            ) from exc
        finally:
            if session is not None:
                session.lock()

        active_ids = {vault.id for vault in self.initialize()}
        restored_id = archived.vault.id
        target_directory = self._managed_directory / restored_id
        if restored_id in active_ids or target_directory.exists():
            restored_id = str(uuid4())
            target_directory = self._managed_directory / restored_id
        restored = ManagedVault(
            id=restored_id,
            name=clean_name,
            storage_kind=MANAGED_STORAGE,
            created_at=archived.vault.created_at,
        )
        archive_directory = self._archive_directory(archive_key)
        moved: list[tuple[Path, Path]] = []
        try:
            self._managed_directory.mkdir(parents=True, exist_ok=True)
            self._managed_directory.chmod(0o700)
            stored_directory = archive_directory / "storage"
            if stored_directory.is_dir():
                os.replace(stored_directory, target_directory)
                moved.append((target_directory, stored_directory))
            else:
                target_directory.mkdir(parents=False, exist_ok=False)
                target_directory.chmod(0o700)
                target_database = target_directory / "vault.db"
                os.replace(source_database, target_database)
                moved.append((target_database, source_database))
                archived_backups = archive_directory / "backups"
                if archived_backups.is_dir():
                    target_backups = target_directory / "backups"
                    os.replace(archived_backups, target_backups)
                    moved.append((target_backups, archived_backups))
            (target_directory / "vault.db").chmod(0o600)
            updated = [*self.initialize(), restored]
            self._save(updated)
        except (OSError, VaultCatalogError) as exc:
            for source, destination in reversed(moved):
                if source.exists() and not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
            try:
                target_directory.rmdir()
            except OSError:
                pass
            raise VaultCatalogError(
                "Não foi possível restaurar o cofre arquivado com segurança."
            ) from exc
        self._vaults = updated
        self._cleanup_restored_archive(archive_directory)
        return restored

    def vault_path(self, vault: ManagedVault) -> Path:
        self._validate_record(vault)
        if vault.storage_kind == LEGACY_STORAGE:
            return self._legacy_vault_path
        return self._managed_directory / vault.id / "vault.db"

    def backup_directory(self, vault: ManagedVault) -> Path:
        self._validate_record(vault)
        if vault.storage_kind == LEGACY_STORAGE:
            return self._legacy_backup_directory
        return self._managed_directory / vault.id / "backups"

    def _load(self) -> list[ManagedVault]:
        try:
            document = json.loads(self._catalog_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or set(document) != {"version", "vaults"}:
                raise ValueError("Estrutura desconhecida.")
            if document["version"] != CATALOG_VERSION or not isinstance(
                document["vaults"], list
            ):
                raise ValueError("Versão de catálogo incompatível.")
            vaults = [ManagedVault.from_dict(item) for item in document["vaults"]]
            self._validate_collection(vaults)
            return vaults
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise VaultCatalogError("O catálogo local de cofres é inválido.") from exc

    def _save(self, vaults: list[ManagedVault]) -> None:
        self._validate_collection(vaults)
        self._catalog_path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "version": CATALOG_VERSION,
            "vaults": [vault.to_dict() for vault in vaults],
        }
        self._write_json_atomic(self._catalog_path, document)

    @staticmethod
    def _write_json_atomic(path: Path, document: object) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, path)
        except OSError as exc:
            raise VaultCatalogError("Não foi possível salvar metadados de cofres.") from exc
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    def _load_archived(self, directory: Path) -> ArchivedVault | None:
        if not directory.is_dir() or directory.is_symlink():
            return None
        resolved = directory.resolve()
        if resolved.parent != self._archived_directory.resolve():
            return None
        database_path = self._database_in_archive(resolved)
        if database_path is None:
            return None
        manifest_path = resolved / ARCHIVE_MANIFEST_NAME
        if manifest_path.is_file():
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or set(document) != {
                "version",
                "archived_at",
                "vault",
            }:
                raise ValueError("Manifesto de arquivo inválido.")
            if document["version"] != ARCHIVE_MANIFEST_VERSION or not isinstance(
                document["archived_at"], str
            ):
                raise ValueError("Versão de manifesto incompatível.")
            archived_at = datetime.fromisoformat(document["archived_at"])
            vault = ManagedVault.from_dict(document["vault"])
            self._validate_record(vault)
            return ArchivedVault(
                archive_key=directory.name,
                vault=vault,
                archived_at=archived_at.isoformat(),
                has_manifest=True,
            )

        # Compatibilidade com pastas criadas pelo KeyCiphra 0.7.0.
        prefix, separator, vault_id = directory.name.rpartition("_")
        if not separator:
            return None
        UUID(vault_id)
        try:
            archived_at = datetime.strptime(prefix, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            archived_at = datetime.fromtimestamp(database_path.stat().st_mtime, UTC)
        return ArchivedVault(
            archive_key=directory.name,
            vault=ManagedVault(
                id=vault_id,
                name=f"Cofre arquivado em {archived_at.astimezone().strftime('%d/%m/%Y')}",
                storage_kind=(
                    MANAGED_STORAGE if (resolved / "storage").is_dir() else LEGACY_STORAGE
                ),
                created_at=datetime.fromtimestamp(database_path.stat().st_mtime, UTC).isoformat(),
            ),
            archived_at=archived_at.isoformat(),
            has_manifest=False,
        )

    def _archived_database_path(self, archived: ArchivedVault) -> Path:
        directory = self._archive_directory(archived.archive_key)
        database_path = self._database_in_archive(directory)
        if database_path is None:
            raise VaultCatalogError("O arquivo do cofre arquivado não foi encontrado.")
        return database_path

    @staticmethod
    def _database_in_archive(directory: Path) -> Path | None:
        for candidate in (directory / "storage" / "vault.db", directory / "vault.db"):
            if candidate.is_file() and not candidate.is_symlink():
                return candidate
        return None

    def _archive_directory(self, archive_key: str) -> Path:
        self._validate_archive_key(archive_key)
        directory = (self._archived_directory / archive_key).resolve()
        if directory.parent != self._archived_directory.resolve():
            raise VaultCatalogError("Identificador de arquivo inválido.")
        return directory

    @staticmethod
    def _validate_archive_key(archive_key: str) -> None:
        if (
            not isinstance(archive_key, str)
            or not archive_key
            or Path(archive_key).name != archive_key
            or archive_key in {".", ".."}
        ):
            raise VaultCatalogError("Identificador de arquivo inválido.")

    @staticmethod
    def _cleanup_restored_archive(directory: Path) -> None:
        try:
            (directory / ARCHIVE_MANIFEST_NAME).unlink(missing_ok=True)
            directory.rmdir()
        except OSError:
            pass

    def _validate_collection(self, vaults: list[ManagedVault]) -> None:
        ids: set[str] = set()
        names: set[str] = set()
        legacy_count = 0
        for vault in vaults:
            self._validate_record(vault)
            name_key = vault.name.casefold()
            if vault.id in ids or name_key in names:
                raise ValueError("O catálogo possui cofres duplicados.")
            ids.add(vault.id)
            names.add(name_key)
            legacy_count += vault.storage_kind == LEGACY_STORAGE
        if legacy_count > 1:
            raise ValueError("O catálogo possui mais de um cofre histórico.")

    def _validate_record(self, vault: ManagedVault) -> None:
        if not isinstance(vault, ManagedVault):
            raise TypeError("Registro de cofre inválido.")
        try:
            UUID(vault.id)
            datetime.fromisoformat(vault.created_at)
        except ValueError as exc:
            raise ValueError("Identificador ou data do cofre são inválidos.") from exc
        if vault.storage_kind not in SUPPORTED_STORAGE_KINDS:
            raise ValueError("Tipo de armazenamento desconhecido.")
        self._validate_name(vault.name)

    def _validate_name(self, name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("O nome do cofre deve ser um texto.")
        clean = " ".join(name.split())
        if not clean:
            raise VaultNameError("Digite um nome para identificar o cofre.")
        if len(clean) > MAXIMUM_VAULT_NAME_LENGTH:
            raise VaultNameError(
                f"Use no máximo {MAXIMUM_VAULT_NAME_LENGTH} caracteres no nome do cofre."
            )
        if any(ord(character) < 32 for character in clean):
            raise VaultNameError("O nome do cofre contém caracteres inválidos.")
        return clean

    def _reject_duplicate_name(self, name: str, *, excluding_id: str | None = None) -> None:
        key = name.casefold()
        if any(
            vault.id != excluding_id and vault.name.casefold() == key
            for vault in self.initialize()
        ):
            raise VaultNameError("Já existe um cofre com esse nome.")

    @staticmethod
    def _remove_new_vault_files(database_path: Path) -> None:
        for candidate in (
            database_path,
            database_path.with_name(f"{database_path.name}-wal"),
            database_path.with_name(f"{database_path.name}-shm"),
        ):
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            database_path.parent.rmdir()
        except OSError:
            pass
