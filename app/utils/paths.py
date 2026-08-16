"""Caminhos de dados do usuário e recursos empacotados."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

APPLICATION_NAME = "KeyCiphra"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DATA_DIRECTORY = PROJECT_ROOT / "data"
LEGACY_VAULT_PATH = LEGACY_DATA_DIRECTORY / "vault.db"
LEGACY_BACKUP_DIRECTORY = PROJECT_ROOT / "backups"


def resolve_application_data_directory(
    *,
    platform_name: str | None = None,
    environment: Mapping[str, str] | None = None,
    home_directory: Path | None = None,
) -> Path:
    """Retorna uma pasta gravável e privada por usuário para cada sistema."""
    platform_value = platform_name or sys.platform
    values = environment if environment is not None else os.environ
    home = Path(home_directory) if home_directory is not None else Path.home()

    if platform_value == "win32":
        local_app_data = values.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else home / "AppData" / "Local"
    elif platform_value == "darwin":
        base = home / "Library" / "Application Support"
    else:
        xdg_data_home = values.get("XDG_DATA_HOME")
        base = Path(xdg_data_home) if xdg_data_home else home / ".local" / "share"
    return base / APPLICATION_NAME


def resource_path(relative_path: str | Path) -> Path:
    """Resolve recursos tanto no código-fonte quanto no bundle do PyInstaller."""
    bundle_root = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return bundle_root / Path(relative_path)


APPLICATION_DATA_DIRECTORY = resolve_application_data_directory()
DATA_DIRECTORY = APPLICATION_DATA_DIRECTORY / "data"
DEFAULT_VAULT_PATH = DATA_DIRECTORY / "vault.db"
BACKUP_DIRECTORY = APPLICATION_DATA_DIRECTORY / "backups"
VAULT_CATALOG_PATH = APPLICATION_DATA_DIRECTORY / "vaults.json"
MANAGED_VAULTS_DIRECTORY = APPLICATION_DATA_DIRECTORY / "vaults"
ARCHIVED_VAULTS_DIRECTORY = APPLICATION_DATA_DIRECTORY / "archived-vaults"
LOG_DIRECTORY = APPLICATION_DATA_DIRECTORY / "logs"
SETTINGS_PATH = APPLICATION_DATA_DIRECTORY / "settings.json"
INSTANCE_LOCK_PATH = APPLICATION_DATA_DIRECTORY / ".keyciphra.lock"
APP_ICON_PATH = resource_path("assets/keyciphra.ico")
