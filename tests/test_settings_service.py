"""Testes das preferências locais não sensíveis."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.app_settings import AppSettings
from app.services.settings_service import SettingsError, SettingsService


def test_missing_file_uses_secure_defaults(tmp_path: Path) -> None:
    settings = SettingsService(tmp_path / "settings.json").load()

    assert settings == AppSettings(
        auto_lock_minutes=5,
        clipboard_seconds=25,
        backup_retention=10,
    )


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "preferences" / "settings.json"
    service = SettingsService(path)
    expected = AppSettings(
        auto_lock_minutes=12,
        clipboard_seconds=40,
        backup_retention=7,
    )

    service.save(expected)

    assert service.load() == expected
    contents = path.read_text(encoding="utf-8")
    assert "password" not in contents.casefold()
    assert "senha" not in contents.casefold()


@pytest.mark.parametrize(
    "values",
    (
        {"auto_lock_minutes": 0},
        {"auto_lock_minutes": 61},
        {"clipboard_seconds": 9},
        {"clipboard_seconds": 121},
        {"backup_retention": 0},
        {"backup_retention": 51},
        {"auto_lock_minutes": True},
    ),
)
def test_settings_reject_unsafe_values(values: dict[str, object]) -> None:
    defaults: dict[str, object] = {
        "auto_lock_minutes": 5,
        "clipboard_seconds": 25,
        "backup_retention": 10,
    }
    defaults.update(values)

    with pytest.raises((TypeError, ValueError)):
        AppSettings(**defaults)  # type: ignore[arg-type]


def test_invalid_file_is_reported_without_overwriting_it(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{conteudo invalido", encoding="utf-8")

    with pytest.raises(SettingsError):
        SettingsService(path).load()

    assert path.read_text(encoding="utf-8") == "{conteudo invalido"
