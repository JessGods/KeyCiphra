"""Testes dos caminhos graváveis usados fora do código-fonte."""

from pathlib import Path

from app.utils.paths import resolve_application_data_directory


def test_windows_uses_local_app_data() -> None:
    resolved = resolve_application_data_directory(
        platform_name="win32",
        environment={"LOCALAPPDATA": r"C:\Users\Teste\AppData\Local"},
        home_directory=Path(r"C:\Users\Teste"),
    )

    assert resolved == Path(r"C:\Users\Teste\AppData\Local") / "KeyCiphra"


def test_windows_has_safe_fallback_without_environment_variable() -> None:
    home = Path(r"C:\Users\Teste")

    resolved = resolve_application_data_directory(
        platform_name="win32",
        environment={},
        home_directory=home,
    )

    assert resolved == home / "AppData" / "Local" / "KeyCiphra"


def test_linux_respects_xdg_data_home() -> None:
    resolved = resolve_application_data_directory(
        platform_name="linux",
        environment={"XDG_DATA_HOME": "/tmp/keyciphra-test-data"},
        home_directory=Path("/home/teste"),
    )

    assert resolved == Path("/tmp/keyciphra-test-data") / "KeyCiphra"
