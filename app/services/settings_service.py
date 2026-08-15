"""Persistência atômica de preferências que não contêm segredos."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from app.models.app_settings import AppSettings


class SettingsError(RuntimeError):
    """Indica leitura ou gravação inválida das preferências."""


class SettingsService:
    def __init__(self, settings_path: Path) -> None:
        self._settings_path = Path(settings_path)

    def load(self) -> AppSettings:
        if not self._settings_path.is_file():
            return AppSettings()
        try:
            values = json.loads(self._settings_path.read_text(encoding="utf-8"))
            if not isinstance(values, dict):
                raise ValueError("A raiz das configurações deve ser um objeto.")
            return AppSettings.from_dict(values)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise SettingsError("As configurações locais são inválidas.") from exc

    def save(self, settings: AppSettings) -> None:
        if not isinstance(settings, AppSettings):
            raise TypeError("Configurações inválidas.")
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._settings_path.with_name(
            f".{self._settings_path.name}.{uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(
                json.dumps(settings.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, self._settings_path)
        except OSError as exc:
            raise SettingsError("Não foi possível salvar as configurações.") from exc
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
