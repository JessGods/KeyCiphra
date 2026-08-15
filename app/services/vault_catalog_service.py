"""Catálogo atômico e caminhos isolados para múltiplos cofres."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

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
MAXIMUM_VAULT_NAME_LENGTH = 48


class VaultCatalogError(RuntimeError):
    """Indica catálogo inválido ou uma alteração que não pôde ser persistida."""


class VaultNameError(ValueError):
    """Indica nome vazio, duplicado ou inadequado para exibição."""


class VaultArchiveAuthenticationError(VaultCatalogError):
    """Evita arquivar um cofre sem confirmar sua senha mestra."""


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

        archive_path = self._archived_directory / (
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{vault.id}"
        )
        moved: list[tuple[Path, Path]] = []
        try:
            archive_path.mkdir(parents=True, exist_ok=False)
            self._archived_directory.chmod(0o700)
            archive_path.chmod(0o700)
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
                archive_path.rmdir()
            except OSError:
                pass
            raise VaultCatalogError("Não foi possível arquivar o cofre com segurança.") from exc
        self._vaults = updated
        return archive_path

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
        temporary = self._catalog_path.with_name(
            f".{self._catalog_path.name}.{uuid4().hex}.tmp"
        )
        document = {
            "version": CATALOG_VERSION,
            "vaults": [vault.to_dict() for vault in vaults],
        }
        try:
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, self._catalog_path)
        except OSError as exc:
            raise VaultCatalogError("Não foi possível salvar o catálogo de cofres.") from exc
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
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
