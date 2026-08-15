"""Testes das permissões privadas do armazenamento."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.security import file_permissions
from app.security.file_permissions import (
    PrivateStoragePermissionError,
    secure_private_directory,
)


@pytest.mark.skipif(os.name == "nt", reason="Bits POSIX não são aplicados pelo Windows.")
def test_posix_permissions_are_restricted_recursively(tmp_path: Path) -> None:
    private = tmp_path / "KeyCiphra"
    child_directory = private / "data"
    child_directory.mkdir(parents=True)
    child_file = child_directory / "vault.db"
    child_file.write_bytes(b"conteudo-ficticio")

    secure_private_directory(private, platform_name="linux")

    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    assert stat.S_IMODE(child_directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(child_file.stat().st_mode) == 0o600


def test_windows_uses_absolute_icacls_and_only_expected_sids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = tmp_path / "KeyCiphra"
    system32 = tmp_path / "Windows" / "System32"
    system32.mkdir(parents=True)
    (system32 / "icacls.exe").write_bytes(b"executavel-ficticio")
    recorded: list[list[str]] = []

    monkeypatch.setattr(file_permissions, "_current_windows_user_sid", lambda: "S-1-5-21-42")
    monkeypatch.setattr(file_permissions, "_windows_system_directory", lambda: system32)

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        recorded.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(file_permissions.subprocess, "run", fake_run)

    secure_private_directory(private, platform_name="win32")

    assert len(recorded) == 1
    command = recorded[0]
    assert Path(command[0]) == system32 / "icacls.exe"
    assert "/inheritance:r" in command
    assert "*S-1-5-21-42:(OI)(CI)F" in command
    assert "*S-1-5-18:(OI)(CI)F" in command
    assert "*S-1-5-32-544:(OI)(CI)F" in command
    assert "/T" not in command


def test_windows_acl_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = tmp_path / "KeyCiphra"
    system32 = tmp_path / "Windows" / "System32"
    system32.mkdir(parents=True)
    (system32 / "icacls.exe").write_bytes(b"executavel-ficticio")
    monkeypatch.setattr(file_permissions, "_current_windows_user_sid", lambda: "S-1-5-21-42")
    monkeypatch.setattr(file_permissions, "_windows_system_directory", lambda: system32)
    monkeypatch.setattr(
        file_permissions.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 5, "", "negado"),
    )

    with pytest.raises(PrivateStoragePermissionError):
        secure_private_directory(private, platform_name="win32")
