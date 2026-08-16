"""Permissões privadas para cofres, backups, configurações e logs."""

from __future__ import annotations

import stat
import subprocess  # nosec B404
import sys
from pathlib import Path


class PrivateStoragePermissionError(RuntimeError):
    """Indica que o armazenamento não pôde ser restringido ao usuário."""


def secure_private_directory(
    directory: Path,
    *,
    platform_name: str | None = None,
) -> None:
    """Remove herança ampla no Windows ou aplica 0700/0600 em sistemas POSIX."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    resolved = target.resolve()
    _validate_target(resolved)
    try:
        if (platform_name or sys.platform) == "win32":
            _restrict_windows_acl(resolved)
        else:
            _restrict_posix_modes(resolved)
    except (OSError, ValueError) as exc:
        raise PrivateStoragePermissionError(
            "Não foi possível restringir as permissões do armazenamento privado."
        ) from exc


def _validate_target(directory: Path) -> None:
    home = Path.home().resolve()
    if directory == directory.parent or directory == home:
        raise ValueError("O diretório privado não pode ser uma raiz ou a pasta pessoal inteira.")


def _restrict_posix_modes(directory: Path) -> None:
    directory.chmod(stat.S_IRWXU)
    for child in directory.rglob("*"):
        if child.is_symlink():
            raise ValueError("Links simbólicos não são permitidos no armazenamento privado.")
        child.chmod(stat.S_IRWXU if child.is_dir() else stat.S_IRUSR | stat.S_IWUSR)


def _restrict_windows_acl(directory: Path) -> None:
    user_sid = _current_windows_user_sid()
    icacls = _windows_system_directory() / "icacls.exe"
    if not icacls.is_file():
        raise OSError("icacls.exe não foi encontrado.")
    grants = (
        f"*{user_sid}:(OI)(CI)F",
        "*S-1-5-18:(OI)(CI)F",
        "*S-1-5-32-544:(OI)(CI)F",
    )
    # O executável é absoluto, os argumentos são uma lista e shell=False.
    result = subprocess.run(  # nosec B603
        [
            str(icacls),
            str(directory),
            "/inheritance:r",
            "/grant:r",
            *grants,
            "/Q",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise OSError("O Windows recusou a atualização das permissões do KeyCiphra.")


def _windows_system_directory() -> Path:
    import ctypes
    from ctypes import wintypes

    buffer = ctypes.create_unicode_buffer(32_768)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetSystemDirectoryW.restype = wintypes.UINT
    length = kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length <= 0 or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "GetSystemDirectoryW falhou.")
    return Path(buffer.value)


def _current_windows_user_sid() -> str:
    import ctypes
    from ctypes import wintypes

    token_query = 0x0008
    token_user_class = 1
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), token_query, ctypes.byref(token)):
        raise OSError(ctypes.get_last_error(), "OpenProcessToken falhou.")
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, token_user_class, None, 0, ctypes.byref(size))
        if size.value == 0:
            raise OSError(ctypes.get_last_error(), "GetTokenInformation falhou.")
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token,
            token_user_class,
            buffer,
            size,
            ctypes.byref(size),
        ):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation falhou.")
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents.value
        string_sid = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid_pointer, ctypes.byref(string_sid)):
            raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW falhou.")
        try:
            return str(string_sid.value)
        finally:
            kernel32.LocalFree(ctypes.cast(string_sid, ctypes.c_void_p))
    finally:
        kernel32.CloseHandle(token)
