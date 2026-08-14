"""Caminhos locais usados pela aplicação."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"
DEFAULT_VAULT_PATH = DATA_DIRECTORY / "vault.db"
BACKUP_DIRECTORY = PROJECT_ROOT / "backups"
